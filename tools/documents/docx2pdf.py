#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 文档转 PDF 工具（带缓存检查）

支持 WPS、Microsoft Word 和 LibreOffice，将 docx/doc 转为 PDF，默认 WPS。
无需额外 Python 依赖。支持单文件、多文件、目录批量转换、通配符筛选。
COM 引擎批量复用实例；缓存区分转换引擎。

用法:
    python docx2pdf.py "文件.docx"
    python docx2pdf.py "文件1.docx" "文件2.doc"
    python docx2pdf.py "D:\\某个目录"
    python docx2pdf.py "D:\\某个目录\\No.9*"          # 通配符筛选
    python docx2pdf.py "文件.docx" --force
    python docx2pdf.py "文件.docx" -o "D:\\输出目录"
    python docx2pdf.py "文件.docx" --names "输出名.pdf"

输出:
    默认: .local/word-pdf/<路径命名>.pdf（LEARNING_TOOLS_DATA_DIR 可覆盖）
    自定义输出目录: <输出目录>\\<原文件名>.pdf
    退出码: 全部成功为 0，任一转换失败为 1

依赖:
    Microsoft Word + PowerShell（Windows 自带）
"""

import sys
import re
import argparse
import base64
import json
import subprocess
import tempfile
import hashlib
import shutil
import os
from pathlib import Path

# 默认配置
DATA_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[2] / ".local")))
DEFAULT_OUTPUT_DIR = DATA_DIR / "word-pdf"
WORD_EXTENSIONS = {".docx", ".doc"}
DEFAULT_ENGINE = "wps"
ENGINE_CHOICES = ("auto", "wps", "office", "libreoffice")
CACHE_DIR = DATA_DIR / "office-cache"
WORK_DIR = DATA_DIR / "office-work"


def add_engine_arguments(parser, default="office"):
    parser.add_argument("--engine", choices=ENGINE_CHOICES, default=default,
                        help=f"转换引擎 (默认: {default})；office 调用 Microsoft Office")
    parser.add_argument("--timeout", type=int, default=None,
                        help="每批 COM 或每文件 LibreOffice 转换超时秒数，必须为正整数")
    parser.add_argument("--libreoffice-path", help="LibreOffice soffice.com/soffice.exe 路径")


def find_libreoffice(explicit=None):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"LibreOffice 程序不存在: {path}")
        return path
    candidates = [shutil.which("soffice.com"), shutil.which("soffice")]
    if os.environ.get("LIBREOFFICE_PATH"):
        candidates.append(os.environ["LIBREOFFICE_PATH"])
    for key in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(key):
            candidates.append(str(Path(os.environ[key]) / "LibreOffice/program/soffice.com"))
    for value in candidates:
        if value and Path(value).is_file():
            return Path(value).resolve()
    raise ValueError("未找到 LibreOffice，请指定 --libreoffice-path")


def resolve_engine(engine, kind="word", libreoffice_path=None):
    if engine not in ENGINE_CHOICES:
        raise ValueError(f"未知引擎: {engine}")
    if engine != "auto":
        if engine == "libreoffice":
            find_libreoffice(libreoffice_path)
        return engine
    import winreg
    progids = {"word": ("KWPS.Application", "Word.Application"),
               "ppt": ("KWPP.Application", "PowerPoint.Application")}
    for candidate, progid in zip(("wps", "office"), progids[kind]):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + "\\CLSID"):
                return candidate
        except FileNotFoundError:
            pass
    find_libreoffice(libreoffice_path)
    return "libreoffice"


def _cache_path(dst):
    key = hashlib.sha256(str(dst.resolve()).casefold().encode("utf-8")).hexdigest()
    return CACHE_DIR / (key + ".json")


def _cache_signature(src, dst, engine, libreoffice_path=None):
    src_stat, dst_stat = src.stat(), dst.stat()
    return {"schema": 1, "source": str(src.resolve()), "source_size": src_stat.st_size,
            "source_mtime_ns": src_stat.st_mtime_ns, "engine": engine,
            "libreoffice_path": str(find_libreoffice(libreoffice_path)) if engine == "libreoffice" else None,
            "output_size": dst_stat.st_size, "output_mtime_ns": dst_stat.st_mtime_ns}


def is_pdf_cached(src, dst, engine, libreoffice_path=None):
    try:
        if not dst.is_file() or dst.stat().st_size == 0:
            return False
        data = json.loads(_cache_path(dst).read_text(encoding="utf-8"))
        return data == _cache_signature(src, dst, engine, libreoffice_path)
    except (OSError, ValueError):
        return False


def _record_cache(src, dst, engine, libreoffice_path=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(dst).write_text(json.dumps(_cache_signature(src, dst, engine, libreoffice_path),
                                         ensure_ascii=False, indent=2), encoding="utf-8")


def _valid_pdf(path):
    if not path.is_file() or path.stat().st_size == 0:
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def _sanitize(name: str) -> str:
    """清理路径组件中的不安全字符"""
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip().rstrip('.')
    if not name:
        return '_'
    _RESERVED = {'CON', 'PRN', 'AUX', 'NUL',
                 *(f'COM{i}' for i in range(1, 10)),
                 *(f'LPT{i}' for i in range(1, 10))}
    if name.split('.')[0].upper() in _RESERVED:
        name = f'_{name}'
    return name


def path_to_filename(file_path: Path) -> str:
    """将文件完整路径转换为确定性的文件名（去盘符、去扩展名、路径分隔符→下划线）"""
    parts = file_path.resolve().with_suffix('').parts[1:]
    return "_".join(_sanitize(p) for p in parts)


def collect_files(inputs: list[str], extensions: set[str] = None) -> list[Path]:
    """从输入参数收集所有待转换的文件路径，支持通配符"""
    if extensions is None:
        extensions = WORD_EXTENSIONS
    files = []
    for item in inputs:
        p = Path(item).resolve()
        if p.is_dir():
            for ext in sorted(extensions):
                files.extend(sorted(p.glob(f"*{ext}")))
        elif p.is_file():
            if p.suffix.lower() in extensions:
                files.append(p)
            else:
                print(f"⚠️ 跳过非目标文件: {p.name}")
        elif p.parent.is_dir() and any(c in p.name for c in '*?['):
            # 通配符模式：父目录存在且文件名含通配符
            matches = sorted(p.parent.glob(p.name))
            matched = [m for m in matches if m.is_file() and m.suffix.lower() in extensions]
            if matched:
                files.extend(matched)
            else:
                print(f"⚠️ 通配符无匹配: {item}")
        else:
            print(f"❌ 路径不存在: {p}")
    return files


def get_output_path(src: Path, out_dir: Path, keep_name: bool) -> Path:
    """根据命名模式计算输出路径"""
    if keep_name:
        return out_dir / f"{src.stem}.pdf"
    else:
        return out_dir / f"{path_to_filename(src)}.pdf"


def _convert_com_batch(pairs, engine, kind, timeout=None):
    """批量复用 Word、PowerPoint 或 WPS COM 实例，原件只读打开。"""
    if not pairs:
        return []

    # 确保所有输出目录存在
    for _, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps([
        {'index': i, 'src': str(src.resolve()), 'dst': str(dst.resolve())}
        for i, (src, dst) in enumerate(pairs)
    ], ensure_ascii=False).encode('utf-8')
    encoded = base64.b64encode(payload).decode('ascii')
    progid = {("word", "office"): "Word.Application", ("word", "wps"): "KWPS.Application",
              ("ppt", "office"): "PowerPoint.Application", ("ppt", "wps"): "KWPP.Application"}[(kind, engine)]
    collection = "Documents" if kind == "word" else "Presentations"
    open_line = ('            $doc = $app.Documents.Open($pair.src, $false, $true)' if kind == "word"
                 else '            $doc = $app.Presentations.Open($pair.src, -1, 0, 0)')
    export_line = ('            $doc.ExportAsFixedFormat($pair.dst, 17)' if kind == "word"
                   else '            $doc.SaveAs($pair.dst, 32)')
    close_line = '                try { $doc.Close(0) } finally {' if kind == "word" else '                try { $doc.Close() } finally {'
    ps_lines = [
        "$ErrorActionPreference = 'Stop'",
        '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)',
        f"$pairs = ConvertFrom-Json ([System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')))",
        '$app = $null',
        '$owned = $false',
        'try {',
        f'    $app = New-Object -ComObject {progid}',
        f'    if ($app.{collection}.Count -ne 0) {{ throw "自动化实例包含已有文档，请关闭对应文档后重试" }}',
        '    $owned = $true',
        '    $app.AutomationSecurity = 3',
        ('    $app.Visible = $false' if kind == "word" else '    $app.DisplayAlerts = 1'),
        ('    $app.DisplayAlerts = 0' if kind == "word" else '    $null = $app.Name'),
        '    foreach ($pair in $pairs) {',
        '        $doc = $null',
        '        try {',
        '            Write-Output "STAGE|$($pair.index)|打开文档"',
        open_line,
        '            Write-Output "STAGE|$($pair.index)|导出 PDF"',
        export_line,
        '            Write-Output "OK|$($pair.index)"',
        '        } catch {',
        '            Write-Output "FAIL|$($pair.index)|$($_.Exception.Message)"',
        '        } finally {',
        '            if ($null -ne $doc) {',
        close_line,
        '                    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null',
        '                }',
        '            }',
        '        }',
        '    }',
        '} finally {',
        '    if ($null -ne $app) {',
        '        try { if ($owned) { $app.Quit() } } finally {',
        '            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null',
        '        }',
        '    }',
        '}',
    ]

    script_content = '\n'.join(ps_lines)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', encoding='utf-8-sig',
                                     delete=False) as handle:
        handle.write(script_content)
        tmp = Path(handle.name)

    results = [False] * len(pairs)
    reported = set()
    try:
        timeout = timeout or max(120, 60 * len(pairs))
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(tmp)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith(('OK|', 'FAIL|')):
                parts = line.split('|', 2)
                idx = int(parts[1])
                reported.add(idx)
                if parts[0] == 'OK':
                    dst = pairs[idx][1]
                    results[idx] = dst.is_file() and dst.stat().st_size > 0
                    if not results[idx]:
                        print(f"  转换失败 {pairs[idx][0].name}: 未生成有效PDF")
                else:
                    err_msg = parts[2] if len(parts) > 2 else '未知错误'
                    print(f"  转换失败 {pairs[idx][0].name}: {err_msg}")
            elif line:
                print(f"  PowerShell输出: {line}")
        if proc.stderr.strip():
            print(f"  PowerShell错误: {proc.stderr.strip()}")
        if proc.returncode != 0:
            print(f"  PowerShell退出码: {proc.returncode}")
            results = [False] * len(pairs)
        for idx in range(len(pairs)):
            if idx not in reported:
                print(f"  转换失败 {pairs[idx][0].name}: 未收到转换结果")
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        stages = [line for line in output.splitlines() if line.startswith("STAGE|")]
        if stages:
            print(f"  最后阶段: {stages[-1]}")
        print(f"  批量转换超时 ({timeout}s)；应用可能仍在运行，请检查对应自动化实例")
    except OSError as exc:
        print(f"  无法运行PowerShell: {exc}")
    finally:
        tmp.unlink(missing_ok=True)

    return results


def _convert_libreoffice(pairs, kind, executable, work, timeout=None):
    results = []
    profile = work / "profile"
    filter_name = "writer_pdf_Export" if kind == "word" else "impress_pdf_Export"
    for index, (src, dst) in enumerate(pairs):
        out = work / f"lo_{index}"
        out.mkdir()
        command = [str(executable), "-env:UserInstallation=" + profile.as_uri(),
                   "--headless", "--nologo", "--norestore", "--convert-to",
                   "pdf:" + filter_name, "--outdir", str(out), str(src.resolve())]
        try:
            proc = subprocess.run(command, capture_output=True, timeout=timeout or 120)
            for stream in (proc.stdout, proc.stderr):
                if stream.strip():
                    try:
                        message = stream.decode("utf-8")
                    except UnicodeDecodeError:
                        message = stream.decode("mbcs" if os.name == "nt" else "utf-8", errors="replace")
                    print(message.strip())
            generated = out / (src.stem + ".pdf")
            ok = proc.returncode == 0 and _valid_pdf(generated)
            if ok:
                shutil.move(str(generated), str(dst))
            else:
                print(f"转换失败 {src.name}: LibreOffice 退出码 {proc.returncode}，或未生成有效 PDF")
            results.append(ok)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"转换失败 {src.name}: {exc}")
            results.append(False)
    return results


def convert_office_batch(pairs, engine, kind="word", timeout=None, libreoffice_path=None):
    if not pairs:
        return []
    try:
        if timeout is not None and timeout <= 0:
            raise ValueError("--timeout 必须为正整数")
        engine = resolve_engine(engine, kind, libreoffice_path)
        executable = find_libreoffice(libreoffice_path) if engine == "libreoffice" else None
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="convert_", dir=WORK_DIR) as directory:
            work = Path(directory)
            staged = [(Path(src), work / f"output_{i}.pdf") for i, (src, _) in enumerate(pairs)]
            print(f"转换引擎: {engine} ({kind})")
            results = (_convert_libreoffice(staged, kind, executable, work, timeout)
                       if engine == "libreoffice" else _convert_com_batch(staged, engine, kind, timeout))
            for index, ((src, dst), (_, temporary)) in enumerate(zip(pairs, staged)):
                if not results[index]:
                    continue
                try:
                    if not _valid_pdf(temporary):
                        raise ValueError("未生成有效 PDF")
                    dst = Path(dst)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(temporary), str(dst))
                    _record_cache(Path(src), dst, engine, libreoffice_path)
                except (OSError, ValueError) as exc:
                    print(f"转换失败 {src.name}: {exc}")
                    results[index] = False
            return results
    except (OSError, ValueError) as exc:
        print(f"转换失败: {exc}")
        return [False] * len(pairs)


def convert_batch(pairs, engine=DEFAULT_ENGINE, timeout=None, libreoffice_path=None):
    return convert_office_batch(pairs, engine, "word", timeout, libreoffice_path)


def convert_one(src, pdf_path, engine=DEFAULT_ENGINE, timeout=None, libreoffice_path=None):
    results = convert_batch([(src, pdf_path)], engine, timeout, libreoffice_path)
    return results[0] if results else False


def main():
    parser = argparse.ArgumentParser(description="Word 文档转 PDF 工具（Word COM）")
    parser.add_argument("inputs", nargs="+", help="文件路径、目录或通配符（支持多个）")
    parser.add_argument("--output", "-o", help="输出目录或单文件输出路径 (默认: %(default)s)",
                        default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--names", nargs="+", help="依次指定每个输入文件对应的输出PDF文件名")
    parser.add_argument("--force", action="store_true",
                        help="强制重新转换，忽略缓存")
    add_engine_arguments(parser, DEFAULT_ENGINE)
    args = parser.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout 必须为正整数")
    try:
        args.engine = resolve_engine(args.engine, "word", args.libreoffice_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"转换引擎: {args.engine}")

    # 收集文件
    files = collect_files(args.inputs)
    if not files:
        print("❌ 未找到任何 Word 文件")
        sys.exit(1)

    if args.names and len(args.names) != len(files):
        print(f"❌ 错误: 指定的输出名称数量 ({len(args.names)}) 与输入文件数量 ({len(files)}) 不一致！")
        sys.exit(1)

    print(f"📋 共 {len(files)} 个文件待处理")

    # 判定输出路径
    out_param = Path(args.output).resolve()
    is_single_file_out = (len(files) == 1 and out_param.suffix.lower() == ".pdf")
    
    if is_single_file_out:
        out_dir = out_param.parent
    else:
        out_dir = out_param
        
    out_dir.mkdir(parents=True, exist_ok=True)

    # 分类：需要转换的 vs 已缓存的
    to_convert = []
    cached_count = 0

    for idx, f in enumerate(files):
        if is_single_file_out:
            pdf_path = out_param
        elif args.names:
            name = args.names[idx]
            if not name.lower().endswith(".pdf"):
                name += ".pdf"
            pdf_path = out_dir / name
        else:
            # 判断是否为自定义输出目录以决定是否保留原名
            if args.output != str(DEFAULT_OUTPUT_DIR):
                pdf_path = out_dir / f"{f.stem}.pdf"
            else:
                pdf_path = out_dir / f"{path_to_filename(f)}.pdf"

        if not args.force and is_pdf_cached(f, pdf_path, args.engine, args.libreoffice_path):
            print(f"已缓存，跳过: {f.name}")
            print(f"   路径: {pdf_path}")
            cached_count += 1
            continue

        to_convert.append((f, pdf_path))

    # 批量转换
    convert_success = 0
    if to_convert:
        print(f"\n🔄 开始转换 {len(to_convert)} 个文件...")
        for src, _ in to_convert:
            print(f"  📝 {src.name}")

        results = convert_batch(to_convert, args.engine, args.timeout, args.libreoffice_path)

        for (src, pdf_path), ok in zip(to_convert, results):
            if ok:
                print(f"✅ 完成: {pdf_path}")
                convert_success += 1

    total_success = cached_count + convert_success
    print(f"\n📊 结果: {total_success}/{len(files)} 成功")
    print(f"   输出目录: {out_dir}")
    sys.exit(0 if total_success == len(files) else 1)


if __name__ == "__main__":
    main()
