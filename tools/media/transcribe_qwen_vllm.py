"""Qwen3-ASR HTTP 客户端：浮动切片、并发请求、VAD 与转录清单。

默认连接或自动启动本地WSL服务；外部兼容服务可用 --url 指定。
环境配置见仓库 README；依赖见 requirements/asr-client.txt。
任务输出包含 transcript.md、chunks.json 和 chunks/。
"""

import argparse
import errno
import json
import math
import os
import subprocess
import sys
import time
import traceback
import urllib.request
import wave
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime
from threading import RLock
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import requests

# ============ 配置区 ============
# ffmpeg/ffprobe 路径（winget 安装 of Gyan.FFmpeg 完整版）
FFMPEG_DIR = os.environ.get("FFMPEG_BIN_DIR", "")
if FFMPEG_DIR and FFMPEG_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

DATA_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[2] / ".local")))
VLLM_URL = os.environ.get("QWEN_ASR_URL", "http://localhost:8000")
MODEL_NAME = os.environ.get("QWEN_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
INPUT_DIR = os.environ.get("LEARNING_AUDIO_DIR", str(DATA_DIR / "audio"))
OUTPUT_DIR = os.environ.get("LEARNING_TRANSCRIPT_DIR", str(DATA_DIR / "transcripts"))
CHUNK_SEC      = 150      # 每块硬上限 2.5 分钟（encoder cache 上限约 2048 token）
MIN_CHUNK_SEC  = 120      # 从此位置起寻找临近上限的低能量切点
BOUNDARY_WINDOW_MS = 100  # 切点能量评估窗口
TARGET_SR      = 16000
AUDIO_EXTS     = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".mp4"}
MAX_WORKERS    = 5        # 默认并发数（RTX 4060 Laptop 8GB 长视频实测最优）

# ============ VAD 过滤配置 ============
VAD_ENABLED    = True     # 是否启用 VAD 过滤大段静音
VAD_THRESHOLD  = 0.4      # 人声概率阈值（0.0 ~ 1.0）
VAD_MIN_SPEECH_SEC = 2.0  # 150s分块内判定为有效语音块的累计人声音频秒数下限
VAD_MODEL_PATH = Path(os.environ.get("SILERO_VAD_MODEL", str(DATA_DIR / "models" / "silero_vad.onnx")))
VAD_MODEL_URL  = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
# ======================================


class TeeStream:
    def __init__(self, terminal, logfile, lock):
        self.terminal = terminal
        self.logfile = logfile
        self.lock = lock

    def write(self, text):
        with self.lock:
            self.terminal.write(text)
            self.logfile.write(text)
            self.terminal.flush()
            self.logfile.flush()
        return len(text)

    def flush(self):
        with self.lock:
            self.terminal.flush()
            self.logfile.flush()

    def __getattr__(self, name):
        return getattr(self.terminal, name)


@contextmanager
def console_log(path):
    if path is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = RLock()
    with path.open("a", encoding="utf-8", buffering=1) as logfile:
        with redirect_stdout(TeeStream(sys.stdout, logfile, lock)), \
                redirect_stderr(TeeStream(sys.stderr, logfile, lock)):
            print(f"运行开始：{datetime.now().isoformat(timespec='seconds')}，日志：{path}")
            try:
                yield
            except BaseException:
                traceback.print_exc()
                raise


class TranscriptionLock:
    """使用操作系统文件锁串行执行跨进程转录批次。"""

    def __init__(self, path: Path = None, poll_interval: float = 2.0):
        self.path = path if path is not None else Path(OUTPUT_DIR).parent / ".vllm_transcription.lock"
        self.poll_interval = poll_interval
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            waiting = False
            while True:
                self.handle.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if not waiting:
                        print("已有转录批次运行，正在等待；可按 Ctrl+C 取消等待。", flush=True)
                        waiting = True
                    time.sleep(self.poll_interval)
                else:
                    if waiting:
                        print("已获得转录锁，开始处理本批音频。", flush=True)
                    return self
        except BaseException:
            self.handle.close()
            self.handle = None
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def download_vad_model() -> bool:
    """如果本地没有 VAD 模型，从 GitHub 自动下载"""
    if not VAD_ENABLED:
        return True
    if VAD_MODEL_PATH.exists():
        return True
    
    print(f"正在从 GitHub 自动下载 Silero VAD 模型...")
    VAD_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(VAD_MODEL_URL, str(VAD_MODEL_PATH))
        print(f"下载成功！模型已保存至：{VAD_MODEL_PATH}")
        return True
    except Exception as e:
        print(f"  [警告] VAD 模型自动下载失败 ({e})")
        print("  您可以手动下载该文件并存放在：")
        print(f"  {VAD_MODEL_PATH}")
        print(f"  下载直链：{VAD_MODEL_URL}\n")
        return False


def read_wav_file(path: Path) -> np.ndarray:
    """读取 ffmpeg 转出来的 WAV 临时文件并归一化为 float32 单声道数据"""
    with wave.open(str(path), 'rb') as w:
        sampwidth = w.getsampwidth()
        n_frames = w.getnframes()
        data = w.readframes(n_frames)
        if sampwidth == 2:
            return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            return np.frombuffer(data, dtype=np.float32)
        else:
            return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


# 全局 VAD Session 单例，避免多线程并发加载死锁
GLOBAL_VAD_SESSION = None

def get_vad_session() -> "ort.InferenceSession":
    global GLOBAL_VAD_SESSION
    if GLOBAL_VAD_SESSION is None:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        # 强制使用 CPU 推理，避免 CUDA 冲突
        GLOBAL_VAD_SESSION = ort.InferenceSession(
            str(VAD_MODEL_PATH), sess_options=opts, providers=['CPUExecutionProvider']
        )
    return GLOBAL_VAD_SESSION


def is_letter(ch: str) -> bool:
    return 'a' <= ch <= 'z' or 'A' <= ch <= 'Z'


def clean_hallucination_repeats(text: str, max_repeats: int = 5) -> str:
    """
    检测并截断连续重复的子串（解决 ASR 幻觉空转）
    """
    if not text:
        return ""
    
    n = len(text)
    i = 0
    res = []
    
    while i < n:
        matched = False
        # 从长到短尝试寻找重复的模式串
        for k in range(40, 0, -1):
            if i + k > n:
                continue
            pattern = text[i : i + k]
            
            # 排除只有空白字符或全是标点的情况
            stripped = pattern.strip(" \t\n\r.,!?，。！？、…()[]{}")
            if not stripped:
                continue
            
            # 边界检查：防止在英文单词内部切断
            if i > 0 and is_letter(text[i-1]) and is_letter(text[i]):
                continue
                
            # 统计连续重复的次数
            count = 1
            nxt = i + k
            while nxt + k <= n and text[nxt : nxt + k] == pattern:
                count += 1
                nxt += k
            
            if count > max_repeats:
                # 检查截断的末尾，防止截断在英文单词内部
                if nxt < n and is_letter(text[nxt-1]) and is_letter(text[nxt]):
                    continue
                # 只保留 2 次，并追加截断提示
                res.append(pattern * 2 + " [已自动截断重复内容] ")
                i = nxt
                matched = True
                break
                
        if not matched:
            res.append(text[i])
            i += 1
            
    return "".join(res).strip()


class SileroVADDetector:
    def __init__(self, session):
        self.session = session
        self.reset()
        
    def reset(self):
        # 隐藏状态: shape [2, 1, 128]
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        # 上下文缓存: 64 个采样点
        self._context = np.zeros((1, 64), dtype=np.float32)
        
    def predict_chunk(self, x: np.ndarray) -> float:
        """
        x: shape (512,), float32 normalized to [-1.0, 1.0]
        """
        if len(x.shape) > 1:
            x = x.squeeze()
        if len(x) < 512:
            x = np.pad(x, (0, 512 - len(x)))
            
        x_2d = np.expand_dims(x, axis=0) # [1, 512]
        x_input = np.concatenate([self._context, x_2d], axis=1) # [1, 576]
        
        ort_inputs = {
            'input': x_input.astype(np.float32),
            'state': self._state,
            'sr': np.array(16000, dtype=np.int64)
        }
        
        ort_outs = self.session.run(None, ort_inputs)
        out, state = ort_outs
        
        self._state = state
        self._context = x_input[:, -64:]
        
        return float(out[0][0])

    def has_speech(self, audio: np.ndarray, threshold: float = 0.4, min_speech_sec: float = 2.0) -> bool:
        """
        对整段音频（150秒的 float32 数据）评估是否包含足够长度的人声。
        """
        self.reset()
        window_size = 512
        speech_frames = 0
        min_speech_frames = int((min_speech_sec * 16000) / window_size)
        
        for i in range(0, len(audio), window_size):
            chunk = audio[i:i + window_size]
            prob = self.predict_chunk(chunk)
            if prob >= threshold:
                speech_frames += 1
                if speech_frames >= min_speech_frames:
                    return True
        return False


def get_wsl_ip() -> str:
    """获取 WSL2 虚拟机的真实网卡 IP"""
    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "hostname", "-I"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.decode('utf-8', errors='ignore')
            ips = output.strip().split()
            if ips:
                return ips[0]
    except Exception:
        pass
    return None


def check_url_health(url: str) -> bool:
    """探测指定 API 终点是否健康，强行旁路系统代理"""
    try:
        r = requests.get(f"{url}/health", timeout=2, proxies={"http": None, "https": None})
        return r.status_code == 200
    except Exception:
        return False


def ensure_server_running(url_arg: str, is_default_url: bool) -> bool:
    """连接已有服务，或按本地配置自动启动 WSL 服务。"""
    from asr_service import ensure_service
    global VLLM_URL
    resolved = ensure_service(url_arg, is_default_url)
    if resolved:
        VLLM_URL = resolved
        return True
    print(f"ASR 服务不可达：{url_arg}。请检查启动日志或 --url 配置。")
    return False



def convert_to_wav(input_path: Path, output_path: Path, start_sec: float = 0,
                   duration_sec: float = None) -> bool:
    """用 ffmpeg 将音频转为 16kHz mono WAV"""
    cmd = ["ffmpeg", "-y", "-nostdin"]
    if start_sec > 0:
        cmd.extend(["-ss", str(start_sec)])
    cmd.extend(["-i", str(input_path)])
    if duration_sec:
        cmd.extend(["-t", str(duration_sec)])
    cmd.extend(["-ar", str(TARGET_SR), "-ac", "1", str(output_path)])
    
    # 丢弃 stdout/stderr/stdin 输出，杜绝缓冲区满或等待 stdin 导致死锁
    result = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def get_audio_duration(path: Path) -> float:
    """用 ffprobe 获取音频时长（秒）"""
    cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def format_timestamp(seconds: float) -> str:
    """时间标签精确到秒；不足一小时省略小时位。"""
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def find_low_energy_boundary(audio_path: Path, start_sec: float,
                             min_chunk_sec: int, max_chunk_sec: int) -> float:
    """在允许区间内选择靠近上限的低能量切点。"""
    search_start = start_sec + min_chunk_sec
    search_duration = max_chunk_sec - min_chunk_sec
    if search_duration <= 0:
        return start_sec + max_chunk_sec

    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-ss", str(search_start),
        "-i", str(audio_path), "-t", str(search_duration),
        "-ar", str(TARGET_SR), "-ac", "1", "-f", "s16le", "pipe:1",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    samples = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
    if result.returncode != 0 or samples.size == 0:
        return start_sec + max_chunk_sec

    window = max(1, int(TARGET_SR * BOUNDARY_WINDOW_MS / 1000))
    n_windows = math.ceil(samples.size / window)
    padded = np.pad(samples, (0, n_windows * window - samples.size))
    energies = np.mean(np.abs(padded.reshape(n_windows, window)), axis=1)

    min_energy = float(np.min(energies))
    tolerance = max(32.0, min_energy * 1.5)
    candidates = np.flatnonzero(energies <= tolerance)
    selected = int(candidates[-1]) if candidates.size else int(np.argmin(energies))
    boundary = search_start + min((selected + 0.5) * window / TARGET_SR, search_duration)
    return min(boundary, start_sec + max_chunk_sec)


def build_chunks(audio_path: Path, total_sec: float, max_chunk_sec: int,
                 min_chunk_sec: int) -> list[tuple[int, float, float]]:
    """生成无重叠、无缺口且不超过上限的浮动音频块。"""
    if min_chunk_sec <= 0 or min_chunk_sec > max_chunk_sec:
        raise ValueError("min_chunk_sec 必须大于 0 且不超过 chunk_sec")

    chunks = []
    start = 0.0
    idx = 0
    while total_sec - start > max_chunk_sec:
        boundary = find_low_energy_boundary(
            audio_path, start, min_chunk_sec, max_chunk_sec
        )
        boundary = max(start + min_chunk_sec, min(boundary, start + max_chunk_sec))
        chunks.append((idx, start, boundary - start))
        start = boundary
        idx += 1
    if total_sec > start:
        chunks.append((idx, start, total_sec - start))
    return chunks


def transcribe_chunk(wav_path: Path, language: str = "zh") -> str:
    """发送 WAV 文件到 vLLM ASR API"""
    # 更新心跳文件，告知 vLLM 看门狗仍在使用
    heartbeat = DATA_DIR / ".vllm_heartbeat"
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.touch(exist_ok=True)

    with open(wav_path, "rb") as f:
        r = requests.post(
            f"{VLLM_URL}/v1/audio/transcriptions",
            files={"file": (wav_path.name, f, "audio/wav")},
            data={
                "model": MODEL_NAME,
                "language": language,
                "repetition_penalty": "1.1",
                "max_tokens": "8192",
            },
            proxies={"http": None, "https": None},
            timeout=600,
        )
    if r.status_code == 200:
        return r.json().get("text", "").strip()
    else:
        print(f"  API 错误 {r.status_code}: {r.text}")
        return ""


def process_one_chunk(audio_path: Path, chunk_idx: int, start_sec: float,
                      duration_sec: float, chunk_path: Path,
                      language: str = "zh") -> tuple[int, str, float]:
    """处理单个音频块：转 WAV → VAD 过滤 → 调 API。"""
    heartbeat = DATA_DIR / ".vllm_heartbeat"
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    try:
        heartbeat.touch(exist_ok=True)
    except Exception:
        pass

    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    if not convert_to_wav(
        audio_path, chunk_path, start_sec=start_sec, duration_sec=duration_sec
    ):
        raise RuntimeError(f"音频分块转换失败：{chunk_path}")

    if VAD_ENABLED and VAD_MODEL_PATH.exists():
        try:
            audio_data = read_wav_file(chunk_path)
            detector = SileroVADDetector(get_vad_session())
            is_speech = detector.has_speech(
                audio_data,
                threshold=VAD_THRESHOLD,
                min_speech_sec=VAD_MIN_SPEECH_SEC,
            )
            if not is_speech:
                return chunk_idx, "", 0.0
        except Exception as e:
            print(f"  [警告] 块 {chunk_idx+1} VAD 检测发生异常（退回常规转录）：{e}")

    t0 = time.time()
    text = transcribe_chunk(chunk_path, language=language)
    elapsed = time.time() - t0
    return chunk_idx, text, elapsed


def transcribe_file(audio_path: Path, output_path: Path, chunk_sec: int,
                    min_chunk_sec: int, max_workers: int,
                    language: str = "zh"):
    """转录单个文件，并保存可供 Forced Aligner 复用的分块清单。"""
    total_sec = get_audio_duration(audio_path)
    if total_sec <= 0:
        print("  无法获取时长，跳过")
        return

    chunks_info = build_chunks(audio_path, total_sec, chunk_sec, min_chunk_sec)
    n_chunks = len(chunks_info)
    workers = min(max_workers, n_chunks)
    mode = f"{workers} 路并发" if workers > 1 else "串行"
    print(
        f"  时长：{total_sec/60:.1f} 分钟，分 {n_chunks} 块"
        f"（{min_chunk_sec}-{chunk_sec} 秒浮动，上限 {chunk_sec} 秒），{mode}"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_dir = output_path.parent / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    silent_count = 0
    t_total_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for idx, start, dur in chunks_info:
            chunk_path = chunk_dir / f"chunk_{idx + 1:04d}.wav"
            future = executor.submit(
                process_one_chunk,
                audio_path,
                idx,
                start,
                dur,
                chunk_path,
                language,
            )
            futures[future] = (idx, start, dur, chunk_path)

        for future in as_completed(futures):
            idx, start, dur, chunk_path = futures[future]
            chunk_idx, text, elapsed = future.result()
            cleaned_text = clean_hallucination_repeats(text, max_repeats=5)
            results[chunk_idx] = {
                "text": cleaned_text,
                "elapsed": elapsed,
                "audio_path": str(chunk_path.resolve()),
            }

            end = start + dur
            label = f"{format_timestamp(start)}–{format_timestamp(end)}"
            prefix = f"[完成 {len(results)}/{n_chunks}] 块 {chunk_idx+1} | {label}"
            if not cleaned_text and elapsed == 0.0:
                silent_count += 1
                print(f"{prefix} | 静音，跳过\n", flush=True)
            else:
                speed = dur / elapsed if elapsed > 0 else 0
                preview = (
                    cleaned_text[:80] + "..."
                    if len(cleaned_text) > 80
                    else cleaned_text
                )
                message = f"{prefix} | 耗时 {elapsed:.1f}s | {speed:.1f}x 实时"
                if preview:
                    message += f"\n  {preview}"
                print(message + "\n", flush=True)

    t_total_elapsed = time.monotonic() - t_total_start
    manifest = {
        "version": 1,
        "source": str(audio_path.resolve()),
        "language": language,
        "duration": round(total_sec, 3),
        "chunk_max_seconds": chunk_sec,
        "chunk_min_seconds": min_chunk_sec,
        "chunks": [],
    }
    markdown_blocks = []
    for idx, start, dur in chunks_info:
        result = results.get(idx, {})
        text = result.get("text", "")
        end = start + dur
        display_text = text or "*(此阶段无人声)*"
        markdown_blocks.append(
            f"[{format_timestamp(start)}-{format_timestamp(end)}]\n\n{display_text}"
        )
        manifest["chunks"].append({
            "index": idx + 1,
            "start": round(start, 3),
            "end": round(end, 3),
            "audio_path": result.get(
                "audio_path", str((chunk_dir / f"chunk_{idx + 1:04d}.wav").resolve())
            ),
            "text": text,
            "silent": not bool(text) and result.get("elapsed", 0.0) == 0.0,
        })

    output_path.write_text("\n\n".join(markdown_blocks) + "\n", encoding="utf-8")
    manifest_path = output_path.parent / "chunks.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    n_valid = sum(1 for item in manifest["chunks"] if item["text"])
    avg_speed = total_sec / t_total_elapsed if t_total_elapsed > 0 else 0
    print(f"转录完成：{len(results)}/{n_chunks} 块，静音跳过 {silent_count} 块")
    print(f"处理耗时：{t_total_elapsed:.1f}s | 整体吞吐：{avg_speed:.1f}x 实时")
    print(f"转录文件：{output_path}（共 {n_valid} 段）")
    print(f"分块清单：{manifest_path}")
    print(f"分块音频：{chunk_dir}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR 转录（vLLM 后端，跨窗口自动等待当前批次完成）"
    )
    parser.add_argument("--file", "-f", default=None,
                        help="指定文件名（在 INPUT_DIR 中），不指定则处理全部")
    parser.add_argument("--overwrite", action="store_true",
                        help="强制重跑，忽略已有结果")
    parser.add_argument("--suffix", "-s", default="_qwen_vllm",
                        help="任务名后缀（默认 _qwen_vllm）")
    parser.add_argument("--chunk", "-c", type=int, default=CHUNK_SEC,
                        help=f"每块硬上限秒数（默认 {CHUNK_SEC}，不可超过 {CHUNK_SEC}）")
    parser.add_argument("--min-chunk", type=int, default=None,
                        help=f"开始寻找低能量切点的秒数（默认 min({MIN_CHUNK_SEC}, --chunk)）")
    parser.add_argument("--language", "-l", default="zh",
                        help="语言（默认 zh，英文传 en）")
    parser.add_argument("--output", "-o", default=None,
                        help="自定义任务名，仅单文件有效")
    parser.add_argument("--url", default=VLLM_URL,
                        help=f"vLLM 服务地址（默认 {VLLM_URL}）")
    parser.add_argument("--workers", "-w", type=int, default=MAX_WORKERS,
                        help=f"并发数（默认 {MAX_WORKERS}）")
    parser.add_argument("--out-dir", "-d", default=None,
                        help="自定义任务目录的父目录（默认使用内置 OUTPUT_DIR）")
    parser.add_argument("--log-file", default=None,
                        help="指定路径时同步保存运行日志，默认只在终端实时显示")
    args = parser.parse_args()

    if args.chunk <= 0 or args.chunk > CHUNK_SEC:
        parser.error(f"--chunk 必须大于 0 且不可超过 {CHUNK_SEC} 秒")
    if args.min_chunk is None:
        args.min_chunk = min(MIN_CHUNK_SEC, args.chunk)
    if args.min_chunk <= 0 or args.min_chunk > args.chunk:
        parser.error("--min-chunk 必须大于 0 且不超过 --chunk")

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True, write_through=True)
    log_path = Path(args.log_file) if args.log_file else None
    with console_log(log_path):
        with TranscriptionLock():
            run_batch(args)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def run_batch(args):
    global VLLM_URL
    VLLM_URL = args.url

    # 检查并确保服务可用
    is_default_url = (args.url == "http://localhost:8000")
    if not ensure_server_running(args.url, is_default_url):
        sys.exit(1)

    # VAD 模型自检与准备
    if VAD_ENABLED:
        download_vad_model()

    input_dir = Path(INPUT_DIR)
    output_root = Path(args.out_dir) if args.out_dir else Path(OUTPUT_DIR)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.file:
        audio_files = []
        file_names = [name.strip() for name in args.file.split(",") if name.strip()]
        for name in file_names:
            target = input_dir / name
            if not target.exists():
                print(f"文件不存在：{target}")
                sys.exit(1)
            audio_files.append(target)
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
        out_path = task_dir / "transcript.md"
        if out_path.exists() and not args.overwrite:
            print(f"跳过：{audio_path.name} → {out_path}"); continue
        print(f"转录：{audio_path.name}")
        transcribe_file(
            audio_path,
            out_path,
            args.chunk,
            args.min_chunk,
            args.workers,
            language=args.language,
        )

    print("全部完成！")


if __name__ == "__main__":
    main()
