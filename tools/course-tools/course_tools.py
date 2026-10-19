"""同济课程工具统一命令行入口。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = SCRIPT_DIR
TARGETS = {
    "yourtj": TOOLS_DIR / "yourtj" / "query_yourtj.py",
    "schedule-export": TOOLS_DIR / "schedule" / "export_schedule.py",
    "schedule-query": TOOLS_DIR / "schedule" / "query_schedule.py",
    "look": TOOLS_DIR / "look" / "download_look.py",
}


def print_help() -> None:
    print(
        """同济课程工具统一入口

用法：
  python course_tools.py yourtj <原 query_yourtj.py 参数>
  python course_tools.py schedule export <原 export_schedule.py 参数>
  python course_tools.py schedule query <原 query_schedule.py 参数>
  python course_tools.py look <原 download_look.py 参数>
  python course_tools.py doctor

示例：
  python course_tools.py yourtj search 软件工程
  python course_tools.py yourtj schedule-search 122 --teacher 朱宏明
  python course_tools.py schedule export -c 122 -f json
  python course_tools.py schedule query 大三上 数据库
  python course_tools.py look search 数据库
  python course_tools.py look download 86038 2026-05-11

帮助：
  python course_tools.py --help
  python course_tools.py yourtj --help
  python course_tools.py schedule export --help
  python course_tools.py schedule query --help
  python course_tools.py look --help

说明：
  yourtj 无需登录；schedule 联网抓取和 look 需要 Firefox 中对应平台的登录态。
  参数会原样传递给现有脚本，统一入口返回原脚本的退出码。
"""
    )


def find_firefox_profiles() -> list[Path]:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    profiles_dir = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
    if not profiles_dir.is_dir():
        return []
    return [path for path in profiles_dir.iterdir() if path.is_dir()]


def run_doctor() -> int:
    failures = 0

    print(f"Python: {sys.executable}")
    if sys.version_info >= (3, 8):
        print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    else:
        print("[FAIL] 需要 Python 3.8 或更高版本")
        failures += 1

    for name, path in TARGETS.items():
        if path.is_file():
            print(f"[OK] {name}: {path}")
        else:
            print(f"[FAIL] {name}: 未找到 {path}")
            failures += 1

    curl_path = shutil.which("curl.exe") or shutil.which("curl")
    if curl_path:
        print(f"[OK] curl: {curl_path}")
    else:
        print("[FAIL] 未找到 curl.exe，look 视频下载不可用")
        failures += 1

    profiles = find_firefox_profiles()
    if not profiles:
        print("[FAIL] 未找到 Firefox 配置目录，课表联网抓取和 look 工具不可用")
        failures += 1
    else:
        print(f"[OK] Firefox 配置目录: {len(profiles)} 个")
        has_cookies = any((profile / "cookies.sqlite").is_file() for profile in profiles)
        has_onesystem_storage = any(
            (
                profile
                / "storage"
                / "default"
                / "https+++1.tongji.edu.cn"
                / "ls"
                / "data.sqlite"
            ).is_file()
            for profile in profiles
        )
        if has_cookies:
            print("[OK] Firefox Cookie 数据库存在；登录态有效性需在实际调用时验证")
        else:
            print("[FAIL] 未找到 Firefox Cookie 数据库")
            failures += 1
        if has_onesystem_storage:
            print("[OK] 检测到一系统本地存储；登录态有效性需在实际调用时验证")
        else:
            print("[WARN] 未检测到一系统本地存储；本地缓存查询仍可用，联网抓取前需在 Firefox 登录一系统")

    if failures:
        print(f"\n诊断完成：{failures} 项失败。")
        return 1
    print("\n诊断完成：基础调用环境正常。")
    return 0


def resolve_target(args: list[str]) -> tuple[Path, list[str]] | None:
    if not args:
        return None
    if args[0] == "yourtj":
        return TARGETS["yourtj"], args[1:]
    if args[0] == "look":
        return TARGETS["look"], args[1:]
    if args[0] == "schedule" and len(args) >= 2:
        if args[1] == "export":
            forwarded_args = args[2:]
            if forwarded_args and forwarded_args[0] in {"list-semesters", "-h", "--help", "help"}:
                return TARGETS["schedule-export"], forwarded_args
            return TARGETS["schedule-export"], ["export", *forwarded_args]
        if args[1] == "query":
            return TARGETS["schedule-query"], args[2:]
    return None


def run_target(script: Path, forwarded_args: list[str]) -> int:
    if not script.is_file():
        print(f"错误：未找到目标脚本：{script}", file=sys.stderr)
        return 1
    command = [sys.executable, str(script), *forwarded_args]
    try:
        result = subprocess.run(command, cwd=script.parent, check=False)
    except OSError as error:
        print(f"错误：无法启动目标脚本：{error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return result.returncode


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        print_help()
        return 0
    if args[0] == "doctor":
        return run_doctor()

    target = resolve_target(args)
    if target is None:
        print("错误：无法识别命令。\n", file=sys.stderr)
        print_help()
        return 2
    return run_target(*target)


if __name__ == "__main__":
    raise SystemExit(main())
