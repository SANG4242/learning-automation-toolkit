"""使用 Qwen3-ForcedAligner 对 ASR 分块清单进行精细时间对齐。"""

import argparse
import os
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ALIGNER_MODEL_DIR = os.environ.get("QWEN_ALIGNER_MODEL", "Qwen/Qwen3-ForcedAligner-0.6B")
DEFAULT_BATCH_SIZE = 4
LANGUAGE_MAP = {
    "zh": "Chinese",
    "chinese": "Chinese",
    "en": "English",
    "english": "English",
    "yue": "Cantonese",
    "cantonese": "Cantonese",
}
TERMINAL_PUNCTUATION = "。！？!?"
SOFT_PUNCTUATION = "，,；;：:"
HALLUCINATION_MARKER = "[已自动截断重复内容]"


def normalize_language(language: str) -> str:
    key = str(language or "Chinese").strip().lower()
    return LANGUAGE_MAP.get(key, language)


def clean_reference_text(text: str) -> str:
    return str(text or "").replace(HALLUCINATION_MARKER, "").strip()


def normalize_alignable_text(text: str) -> str:
    kept = []
    for char in text:
        category = unicodedata.category(char)
        if char == "'" or category.startswith("L") or category.startswith("N"):
            kept.append(char.casefold())
    return "".join(kept)


def split_short_sentences(text: str, preferred_chars: int = 60,
                          hard_limit: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []

    sentences = []
    buffer = []
    for char in text:
        buffer.append(char)
        current = "".join(buffer).strip()
        if char in TERMINAL_PUNCTUATION:
            if current:
                sentences.append(current)
            buffer = []
        elif len(current) >= preferred_chars and char in SOFT_PUNCTUATION:
            sentences.append(current)
            buffer = []
        elif len(current) >= hard_limit:
            sentences.append(current)
            buffer = []

    tail = "".join(buffer).strip()
    if tail:
        sentences.append(tail)
    return sentences


def items_to_sentences(text: str, items: list[dict], chunk_index: int) -> list[dict]:
    units = split_short_sentences(text)
    if not units or not items:
        return []

    item_spans = []
    item_cursor = 0
    for item in items:
        normalized = normalize_alignable_text(item["text"])
        start = item_cursor
        item_cursor += len(normalized)
        item_spans.append((start, item_cursor, item))

    sentences = []
    text_cursor = 0
    for unit in units:
        normalized = normalize_alignable_text(unit)
        if not normalized:
            continue
        unit_start = text_cursor
        unit_end = text_cursor + len(normalized)
        text_cursor = unit_end
        matching = [
            item for start, end, item in item_spans
            if end > unit_start and start < unit_end
        ]
        if not matching:
            continue
        sentences.append({
            "text": unit,
            "start": matching[0]["start"],
            "end": matching[-1]["end"],
            "chunk_start": chunk_index,
            "chunk_end": chunk_index,
        })
    return sentences


def merge_cross_chunk_sentences(sentences: list[dict], hard_limit: int = 100) -> list[dict]:
    merged = []
    for sentence in sentences:
        if (
            merged
            and merged[-1]["chunk_end"] + 1 == sentence["chunk_start"]
            and len(merged[-1]["text"] + sentence["text"]) <= hard_limit
            and not merged[-1]["text"].rstrip().endswith(tuple(TERMINAL_PUNCTUATION))
        ):
            previous = merged[-1]
            previous["text"] += sentence["text"]
            previous["end"] = sentence["end"]
            previous["chunk_end"] = sentence["chunk_end"]
        else:
            merged.append(sentence.copy())
    return merged


def stop_vllm_if_requested(enabled: bool) -> None:
    if not enabled:
        return
    from asr_service import stop_managed_service
    print("停止本工具管理的 ASR 服务，释放对齐需要的显存...")
    stop_managed_service()


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def align_manifest(manifest_path: Path, model_path: str, stop_vllm: bool,
                   batch_size: int) -> tuple[Path, Path]:
    import torch
    from qwen_asr import Qwen3ForcedAligner
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunks = manifest.get("chunks", [])
    if not chunks:
        raise ValueError("分块清单中没有 chunks")

    stop_vllm_if_requested(stop_vllm)
    print(f"加载 Forced Aligner：{model_path}")
    aligner = Qwen3ForcedAligner.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map="cuda:0",
    )
    torch.cuda.reset_peak_memory_stats()
    print(f"模型加载完成，batch size={batch_size}\n")

    raw_records = []
    sentence_records = []
    default_language = normalize_language(manifest.get("language", "Chinese"))
    pending = []

    for position, chunk in enumerate(chunks, start=1):
        text = clean_reference_text(chunk.get("text", ""))
        if not text or chunk.get("silent"):
            print(f"  [{position}/{len(chunks)}] 静音或空文本，跳过")
            continue

        audio_path = Path(chunk["audio_path"])
        if not audio_path.exists():
            raise FileNotFoundError(f"分块音频不存在：{audio_path}")
        pending.append((position, chunk, text, audio_path))

    for batch_start in range(0, len(pending), batch_size):
        batch = pending[batch_start:batch_start + batch_size]
        started = time.time()
        results = aligner.align(
            audio=[str(item[3]) for item in batch],
            text=[item[2] for item in batch],
            language=[default_language] * len(batch),
        )
        torch.cuda.synchronize()
        elapsed = time.time() - started

        batch_label = f"{batch_start + 1}-{batch_start + len(batch)}/{len(pending)}"
        print(f"  [批次 {batch_label}] {len(batch)} 个组块，耗时 {elapsed:.1f}s")

        for (position, chunk, text, _), result in zip(batch, results):
            chunk_index = int(chunk.get("index", position))
            offset = float(chunk.get("start", 0.0))
            chunk_end = float(chunk.get("end", offset))
            chunk_items = []

            for item in result:
                global_start = min(chunk_end, max(offset, offset + float(item.start_time)))
                global_end = min(chunk_end, max(global_start, offset + float(item.end_time)))
                record = {
                    "chunk": chunk_index,
                    "text": item.text,
                    "start": round(global_start, 3),
                    "end": round(global_end, 3),
                }
                raw_records.append(record)
                chunk_items.append(record)

            sentence_records.extend(items_to_sentences(text, chunk_items, chunk_index))
            print(
                f"    [{position}/{len(chunks)}] "
                f"{len(chunk_items)} 个对齐单元"
            )

    sentence_records = merge_cross_chunk_sentences(sentence_records)
    for index, sentence in enumerate(sentence_records, start=1):
        sentence["id"] = f"S{index:05d}"

    if manifest_path.name == "chunks.json":
        alignment_path = manifest_path.parent / "alignment.jsonl"
        sentences_path = manifest_path.parent / "sentences.jsonl"
    else:
        name = manifest_path.name
        base_name = name[:-len(".chunks.json")] if name.endswith(".chunks.json") else manifest_path.stem
        alignment_path = manifest_path.with_name(base_name + ".alignment.jsonl")
        sentences_path = manifest_path.with_name(base_name + ".sentences.jsonl")
    write_jsonl(alignment_path, raw_records)
    write_jsonl(sentences_path, sentence_records)

    peak_memory_gib = torch.cuda.max_memory_allocated() / 1024**3
    print(f"\n字/词级对齐：{alignment_path}")
    print(f"短句级索引：{sentences_path}")
    print(f"PyTorch 峰值显存：{peak_memory_gib:.2f} GiB")
    return alignment_path, sentences_path


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True, write_through=True)
    parser = argparse.ArgumentParser(description="Qwen3 Forced Aligner 分块对齐")
    parser.add_argument("manifest", type=Path, help="转录生成的 .chunks.json 清单")
    parser.add_argument("--model", default=ALIGNER_MODEL_DIR, help="Forced Aligner 模型目录")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"每批对齐的组块数（默认 {DEFAULT_BATCH_SIZE}）",
    )
    parser.add_argument(
        "--stop-vllm",
        action="store_true",
        help="对齐前关闭本机 vLLM 服务以释放显存",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        parser.error(f"分块清单不存在：{args.manifest}")
    if args.batch_size <= 0:
        parser.error("--batch-size 必须大于 0")
    try:
        import torch
    except ImportError:
        parser.error("请先在推理环境安装 PyTorch 与 qwen-asr")
    if not torch.cuda.is_available():
        parser.error("当前环境未检测到 CUDA GPU")

    try:
        align_manifest(
            args.manifest.resolve(),
            args.model,
            args.stop_vllm,
            args.batch_size,
        )
    except Exception as error:
        print(f"对齐失败：{error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
