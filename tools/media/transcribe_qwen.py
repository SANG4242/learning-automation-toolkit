"""
Qwen3-ASR 批量音频转录脚本（分块流式版）
- 模型：Qwen3-ASR-1.7B（无 ForcedAligner，速度优先）
- WAV/FLAC：从磁盘分块读，内存仅占一块（~40MB）
- M4A/MP3 等压缩格式：librosa 一次读入（需 ffmpeg，已在 conda 环境安装）
- 长音频逐块处理，边处理边打印结果，实时看进度
- 任务名后缀：默认 _qwen；每个音频输出到独立任务目录
"""

import os
# 把 conda 环境的 ffmpeg 加进 PATH，让 librosa 能读 m4a/mp3 等压缩格式
if os.environ.get("FFMPEG_BIN_DIR"):
    os.environ["PATH"] = os.environ["FFMPEG_BIN_DIR"] + os.pathsep + os.environ.get("PATH", "")

import argparse
import sys
from pathlib import Path

import numpy as np


# ============ 配置区 ============
DATA_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[2] / ".local")))
ASR_MODEL_DIR = os.environ.get("QWEN_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
INPUT_DIR = os.environ.get("LEARNING_AUDIO_DIR", str(DATA_DIR / "audio"))
OUTPUT_DIR = os.environ.get("LEARNING_TRANSCRIPT_DIR", str(DATA_DIR / "transcripts"))
LANGUAGE       = "Chinese"
DEVICE         = "cuda:0"
DTYPE          = "bfloat16"
MAX_NEW_TOKENS = 1024
MAX_BATCH_SIZE = 1
CHUNK_SEC      = 300        # 每块 5 分钟
TARGET_SR      = 16000
AUDIO_EXTS     = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".mp4"}
# ================================

_asr_model = None


def get_asr_model():
    global _asr_model
    if _asr_model is None:
        import torch
        from qwen_asr import Qwen3ASRModel
        print(f"加载模型：{ASR_MODEL_DIR}")
        _asr_model = Qwen3ASRModel.from_pretrained(
            ASR_MODEL_DIR,
            dtype=getattr(torch, DTYPE),
            device_map=DEVICE,
            max_inference_batch_size=MAX_BATCH_SIZE,
            max_new_tokens=MAX_NEW_TOKENS,
        )
        print("模型加载完成\n")
    return _asr_model


def load_audio(path: Path):
    """
    返回 (orig_sr, total_frames, n_channels, backend)
    WAV/FLAC: backend="sf"，后续分块读
    其他格式: backend=numpy_array，用 PyAV 解码整体存入内存
    """
    import soundfile as sf
    ext = path.suffix.lower()
    if ext in (".wav", ".flac"):
        with sf.SoundFile(str(path)) as f:
            return f.samplerate, len(f), f.channels, "sf"
    else:
        import av
        print("  用 PyAV 解码压缩格式...", flush=True)
        container = av.open(str(path))
        audio_stream = container.streams.audio[0]
        resampler = av.audio.resampler.AudioResampler(
            format="s16", layout="mono", rate=TARGET_SR
        )
        chunks = []
        for frame in container.decode(audio_stream):
            for rf in resampler.resample(frame):
                chunks.append(rf.to_ndarray()[0])
        container.close()
        data = np.concatenate(chunks).astype(np.float32) / 32768.0
        return TARGET_SR, len(data), 1, data


def get_chunk(path: Path, backend, i: int, chunk_frames: int,
              orig_sr: int, n_channels: int) -> np.ndarray:
    if isinstance(backend, np.ndarray):
        # 内存中（m4a 等）
        start = i * chunk_frames
        return backend[start:start + chunk_frames]
    else:
        import soundfile as sf
        # sf 分块读（WAV/FLAC）
        with sf.SoundFile(str(path)) as f:
            f.seek(i * chunk_frames)
            raw = f.read(frames=chunk_frames, dtype="float32", always_2d=True)
        chunk = raw.mean(axis=1) if n_channels > 1 else raw[:, 0]
        if orig_sr != TARGET_SR:
            import librosa
            chunk = librosa.resample(chunk, orig_sr=orig_sr, target_sr=TARGET_SR)
        return chunk


def transcribe_file(audio_path: Path, output_path: Path, language: str | None, chunk_sec: int):
    model = get_asr_model()

    orig_sr, total_frames, n_channels, backend = load_audio(audio_path)
    total_sec    = total_frames / orig_sr
    chunk_frames = int(chunk_sec * orig_sr)
    n_chunks     = int(np.ceil(total_frames / chunk_frames))

    print(f"  时长：{total_sec/60:.1f} 分钟，分 {n_chunks} 块（每块 {chunk_sec//60} 分钟）")
    print(f"  采样率：{orig_sr} Hz\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_lines = []

    with open(output_path, "w", encoding="utf-8") as out:
        for i in range(n_chunks):
            start_frame = i * chunk_frames
            end_frame   = min((i + 1) * chunk_frames, total_frames)
            offset_min  = start_frame / orig_sr / 60
            end_min     = end_frame   / orig_sr / 60
            print(f"  [{i+1}/{n_chunks}] {offset_min:.1f}min-{end_min:.1f}min ...", flush=True)

            chunk = get_chunk(audio_path, backend, i, chunk_frames, orig_sr, n_channels)

            results = model.transcribe(
                audio=(chunk, TARGET_SR),
                language=language,
                return_time_stamps=False,
            )
            result = results[0]
            if i == 0:
                print(f"  检测语言：{result.language}")

            text = result.text.strip()
            if text:
                print(f"    {text}\n")
                out.write(text + "\n")
                out.flush()
                all_lines.append(text)
            else:
                print("  （空）\n")

    print(f"  已保存：{output_path}（共 {len(all_lines)} 段）\n")


def main():
    global CHUNK_SEC

    parser = argparse.ArgumentParser(description="Qwen3-ASR 分块转录")
    parser.add_argument("--file",  "-f", default=None,
                        help="指定文件名（在 INPUT_DIR 中），不指定则处理全部")
    parser.add_argument("--language", "-l", default=LANGUAGE,
                        help=f"语言（默认 {LANGUAGE!r}），传 'auto' 自动检测")
    parser.add_argument("--overwrite", action="store_true",
                        help="强制重跑，忽略已有结果")
    parser.add_argument("--suffix", "-s", default="_qwen",
                        help="任务名后缀（默认 _qwen）")
    parser.add_argument("--chunk", "-c", type=int, default=CHUNK_SEC,
                        help=f"每块秒数（默认 {CHUNK_SEC}）")
    parser.add_argument("--output", "-o", default=None,
                        help="自定义任务名，仅单文件有效")
    parser.add_argument("--out-dir", "-d", default=None,
                        help="自定义任务目录的父目录（默认使用内置 OUTPUT_DIR）")
    args = parser.parse_args()

    language  = None if args.language == "auto" else args.language
    CHUNK_SEC = args.chunk

    input_dir = Path(INPUT_DIR)
    output_root = Path(args.out_dir) if args.out_dir else Path(OUTPUT_DIR)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.file:
        target = input_dir / args.file
        if not target.exists():
            print(f"文件不存在：{target}"); sys.exit(1)
        audio_files = [target]
    else:
        audio_files = sorted(f for f in input_dir.iterdir()
                             if f.suffix.lower() in AUDIO_EXTS)

    if not audio_files:
        print(f"没有找到音频文件：{INPUT_DIR}"); sys.exit(0)

    if args.output and len(audio_files) > 1:
        print("警告：--output 仅对单文件有效"); args.output = None

    print(f"共 {len(audio_files)} 个文件\n")

    for audio_path in audio_files:
        stem = args.output if (args.output and len(audio_files) == 1) \
               else (audio_path.stem + args.suffix)
        task_dir = output_root / stem
        out_path = task_dir / "transcript.txt"
        if out_path.exists() and not args.overwrite:
            print(f"跳过：{audio_path.name} → {out_path}"); continue
        print(f"转录：{audio_path.name}")
        transcribe_file(audio_path, out_path, language, CHUNK_SEC)

    print("全部完成！")


if __name__ == "__main__":
    main()
