"""
faster-whisper 批量音频转录脚本
- 模型：large-v3（短音频）/ large-v3-turbo（长音频）自动选择
- 规则：时长 > AUTO_TURBO_MIN 分钟 → turbo，否则 large-v3
- 模型缓存：D:\\TJU-Notes\\个人项目\\asr-models（不占 C 盘）
- 用法：把音频放在 INPUT_DIR，每个音频在 OUTPUT_DIR 下使用独立任务目录
"""

import os
import sys
import time
from pathlib import Path

# ── 修复 Windows 上 CTranslate2 找不到 CUDA DLL 的问题 ──
_nvidia_base = (
    Path(os.environ.get("APPDATA", ""))
    / "Python"
    / f"Python{sys.version_info.major}{sys.version_info.minor}"
    / "site-packages"
    / "nvidia"
)
_cuda_bins = [
    str(_nvidia_base / sub)
    for sub in ("cublas/bin", "cudnn/bin", "cuda_runtime/bin", "nvrtc/bin")
    if (_nvidia_base / sub).exists()
]
if _cuda_bins:
    os.environ["PATH"] = ";".join(_cuda_bins) + ";" + os.environ.get("PATH", "")

import argparse



# ============ 配置区 ============
DATA_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[2] / ".local")))
MODEL_DIR = os.environ.get("WHISPER_MODEL_DIR", str(DATA_DIR / "models"))
INPUT_DIR = os.environ.get("LEARNING_AUDIO_DIR", str(DATA_DIR / "audio"))
OUTPUT_DIR = os.environ.get("LEARNING_TRANSCRIPT_DIR", str(DATA_DIR / "transcripts"))
LANGUAGE        = "zh"
DEVICE          = "cuda"        # GPU；无 CUDA 改 "cpu"
COMPUTE         = "float16"     # GPU 用 float16；CPU 改 "int8"
AUTO_TURBO_MIN  = 20            # 音频时长超过这个分钟数，自动切换到 turbo（约对应转录时长 >3min）

# 本地模型路径映射（跳过 HuggingFace Hub 联网检查）
_LOCAL_MODEL_PATHS = {
    "large-v3": os.path.join(MODEL_DIR, "models--Systran--faster-whisper-large-v3",
                             "snapshots", "edaa852ec7e145841d8ffdb056a99866b5f0a478"),
    "large-v3-turbo": os.path.join(MODEL_DIR, "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
                                   "snapshots", "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"),
}
# ================================

# 模型懒加载缓存，避免重复加载
_model_cache: dict = {}


def get_audio_duration(audio_path: Path) -> float:
    """用 av 库读取音频时长（秒），无需加载 Whisper 模型。"""
    import av
    with av.open(str(audio_path)) as container:
        return float(container.duration) / 1_000_000  # 微秒 → 秒


def select_model_size(duration_sec: float, override: str | None = None) -> str:
    """根据音频时长自动选择模型；override 不为空时直接使用指定模型。"""
    if override:
        return override
    if duration_sec > AUTO_TURBO_MIN * 60:
        return "large-v3-turbo"
    return "large-v3"


def load_model(model_size: str):
    """懒加载：相同 model_size 只加载一次。优先用本地路径，避免联网。"""
    from faster_whisper import WhisperModel
    if model_size not in _model_cache:
        # 优先使用本地路径（跳过 HuggingFace Hub 联网检查）
        model_path = _LOCAL_MODEL_PATHS.get(model_size)
        if model_path and os.path.isdir(model_path):
            print(f"  加载模型 {model_size}（本地路径）...")
            _model_cache[model_size] = WhisperModel(
                model_path,
                device=DEVICE,
                compute_type=COMPUTE,
            )
        else:
            print(f"  加载模型 {model_size}（首次使用会自动下载）...")
            _model_cache[model_size] = WhisperModel(
                model_size,
                device=DEVICE,
                compute_type=COMPUTE,
                download_root=MODEL_DIR,
            )
        print(f"  {model_size} 加载完成")
    return _model_cache[model_size]


def filter_hallucinations(lines: list[str]) -> list[str]:
    """去掉 Whisper 在音效/静音段产生的重复词幻觉。"""
    import re
    from collections import Counter
    result = []
    for line in lines:
        text = re.sub(r"^\[.*?\]\s*", "", line).strip()
        if not text:
            continue
        # 规则1：最高频字符占比超过 70% 且出现超过 4 次
        if len(text) >= 6:
            _, count = Counter(text).most_common(1)[0]
            if count / len(text) > 0.7 and count > 4:
                continue
        # 规则2：文本是某个短语的纯重复（如"泡泡泡泡"）
        for length in range(1, len(text) // 3 + 1):
            chunk = text[:length]
            if text == chunk * (len(text) // length) and len(text) // length >= 4:
                break
        else:
            result.append(line)
            continue
    return result


def transcribe_file(audio_path: Path, output_path: Path, model_override: str | None = None):
    t_start = time.time()
    # 1. 读时长
    try:
        duration = get_audio_duration(audio_path)
    except Exception:
        duration = 0.0

    # 2. 选模型
    model_size = select_model_size(duration, model_override)
    if model_override:
        flag = f"→ {model_size}（手动指定）"
    elif "turbo" in model_size:
        flag = "→ turbo（自动：长音频）"
    else:
        flag = "→ large-v3（自动：短音频）"
    print(f"\n转录：{audio_path.name}  [{duration/60:.1f} min]  {flag}")

    model = load_model(model_size)

    # 3. 转录
    segments, info = model.transcribe(
        str(audio_path),
        language=LANGUAGE,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    print(f"  检测语言：{info.language}，时长：{info.duration:.1f}s")

    lines = []
    for seg in segments:
        line = f"[{seg.start:06.2f}s-{seg.end:06.2f}s] {seg.text.strip()}"
        print(f"  {line}")
        lines.append(line)

    lines = filter_hallucinations(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    elapsed = time.time() - t_start
    speed = duration / elapsed if elapsed > 0 and duration > 0 else 0
    print(f"  已保存：{output_path}（{len(lines)} 行）")
    print(f"  耗时：{elapsed:.1f}s（音频 {duration:.0f}s），{speed:.1f}x 实时速度")


def main():
    parser = argparse.ArgumentParser(description="faster-whisper 批量转录")
    parser.add_argument(
        "--model", "-m",
        choices=["large-v3", "turbo", "large-v3-turbo"],
        default=None,
        help="指定模型（不传则按时长自动选择）。turbo = large-v3-turbo 的简写",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制重新转录，忽略已有结果",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="自定义任务名，仅对单个文件有效。默认与输入文件同名",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="指定文件名（在 INPUT_DIR 中），不指定则处理全部",
    )
    parser.add_argument(
        "--out-dir", "-d",
        default=None,
        help="自定义任务目录的父目录（默认使用内置 OUTPUT_DIR）",
    )
    args = parser.parse_args()

    # 处理 turbo 简写
    model_override = args.model
    if model_override == "turbo":
        model_override = "large-v3-turbo"

    input_dir = Path(INPUT_DIR)
    output_root = Path(args.out_dir) if args.out_dir else Path(OUTPUT_DIR)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.file:
        target = input_dir / args.file
        if not target.exists():
            print(f"文件不存在：{target}")
            return
        audio_files = [target]
    else:
        audio_files = sorted(
            f for f in input_dir.iterdir()
            if f.suffix.lower() in (".m4a", ".mp3", ".wav", ".flac", ".ogg")
        )

    if not audio_files:
        print(f"没有找到音频文件，请把音频放到：{INPUT_DIR}")
        return

    if args.output and len(audio_files) > 1:
        print("警告：--output 只对单个文件有效，多个文件时忽略该参数")
        args.output = None

    print(f"共找到 {len(audio_files)} 个音频文件")
    t_total = time.time()
    for audio_path in audio_files:
        stem = args.output if (args.output and len(audio_files) == 1) else audio_path.stem
        task_dir = output_root / stem
        out_path = task_dir / "transcript.txt"
        if out_path.exists() and not args.force:
            print(f"跳过（已有结果）：{audio_path.name} → {out_path}")
            continue
        transcribe_file(audio_path, out_path, model_override)

    total_elapsed = time.time() - t_total
    print(f"\n全部完成！总耗时：{total_elapsed:.1f}s（{total_elapsed/60:.1f} 分钟）")


if __name__ == "__main__":
    main()
