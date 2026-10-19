"""ASR service discovery, WSL startup and cooperative shutdown."""
import ipaddress
import os
import subprocess
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(ROOT / ".local"))).resolve()
WSL_DISTRO = os.environ.get("QWEN_WSL_DISTRO", "Ubuntu")


def wsl_path(path):
    path = Path(path).resolve()
    if path.drive:
        return f"/mnt/{path.drive[0].lower()}/" + path.as_posix()[3:]
    return str(path)


def health(url):
    try:
        with requests.Session() as session:
            session.trust_env = False
            return session.get(f"{url.rstrip('/')}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def wsl_url():
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(["wsl", "-d", WSL_DISTRO, "--", "hostname", "-I"], capture_output=True, text=True, timeout=5)
        for value in result.stdout.split():
            try:
                address = ipaddress.ip_address(value)
                if address.version == 4:
                    return f"http://{address}:{os.environ.get('QWEN_ASR_PORT', '8000')}"
            except ValueError:
                continue
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def ensure_service(url, allow_local_management):
    if health(url):
        return url.rstrip("/")
    if not allow_local_management:
        return None
    fallback = wsl_url()
    if fallback and health(fallback):
        print(f"localhost 映射不可达，改用 WSL 地址：{fallback}")
        return fallback
    if os.name != "nt" or os.environ.get("QWEN_ASR_AUTO_START", "1") == "0":
        return None
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    script = os.environ.get("QWEN_ASR_WSL_SCRIPT", wsl_path(Path(__file__).with_name("start_vllm_asr.sh")))
    env_args = [f"QWEN_ASR_DATA_DIR={wsl_path(DATA_DIR)}", f"QWEN_ASR_PORT={os.environ.get('QWEN_ASR_PORT', '8000')}"]
    for name in ("QWEN_ASR_MODEL", "QWEN_ASR_VENV", "QWEN_GPU_MEMORY_UTILIZATION", "QWEN_ASR_IDLE_TIMEOUT", "QWEN_ASR_HOST"):
        if os.environ.get(name):
            env_args.append(f"{name}={os.environ[name]}")
    log = (DATA_DIR / "asr-launch.log").open("ab")
    try:
        subprocess.Popen(["wsl", "-d", WSL_DISTRO, "--", "env", *env_args, "bash", script], stdout=log, stderr=log)
    finally:
        log.close()
    print(f"正在启动 WSL ASR，启动日志：{DATA_DIR / 'asr-launch.log'}", flush=True)
    deadline = time.monotonic() + float(os.environ.get("QWEN_ASR_START_TIMEOUT", "180"))
    while time.monotonic() < deadline:
        for candidate in (url, fallback):
            if candidate and health(candidate):
                return candidate.rstrip("/")
        time.sleep(2)
    return None


def stop_managed_service():
    pid_file = DATA_DIR / "asr-service.pid"
    if not pid_file.exists():
        raise RuntimeError("没有本工具管理的 ASR 服务；请通过原服务管理方式停止它。")
    (DATA_DIR / "asr-stop-request").touch()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if not pid_file.exists():
            return
        time.sleep(1)
    raise RuntimeError("ASR 服务尚未确认退出，请检查服务日志和显存状态。")
