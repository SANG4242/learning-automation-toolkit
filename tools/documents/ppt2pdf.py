#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PPT 演示文稿转 PDF 工具（带缓存检查）

支持 Microsoft PowerPoint、WPS 演示和 LibreOffice，将 pptx/ppt 转为 PDF，默认 PowerPoint。
无需额外 Python 依赖。支持单文件、多文件、目录批量转换、通配符筛选。
复用 docx2pdf.py 的引擎与缓存逻辑，COM 引擎批量复用实例。

用法:
    python ppt2pdf.py "文件.pptx"
    python ppt2pdf.py "文件1.pptx" "文件2.ppt"
    python ppt2pdf.py "D:\\某个目录"
    python ppt2pdf.py "D:\\某个目录\\ch7*"             # 通配符筛选
    python ppt2pdf.py "文件.pptx" --force
    python ppt2pdf.py "文件.pptx" -o "D:\\输出目录" --keep-name

输出:
    默认: .local/slides-pdf/<路径命名>.pdf（LEARNING_TOOLS_DATA_DIR 可覆盖）
    --keep-name: <输出目录>\\<原文件名>.pdf

依赖:
    Microsoft PowerPoint + PowerShell（Windows 自带）
"""

import sys
import re
import argparse
from pathlib import Path
from docx2pdf import add_engine_arguments, resolve_engine, is_pdf_cached, convert_office_batch

# 默认配置
from docx2pdf import DATA_DIR
DEFAULT_OUTPUT_DIR = DATA_DIR / "slides-pdf"
PPT_EXTENSIONS = {".pptx", ".ppt"}


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
        extensions = PPT_EXTENSIONS
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


def convert_batch(pairs, engine="office", timeout=None, libreoffice_path=None):
    return convert_office_batch(pairs, engine, "ppt", timeout, libreoffice_path)


def convert_one(src, pdf_path, engine="office", timeout=None, libreoffice_path=None):
    results = convert_batch([(src, pdf_path)], engine, timeout, libreoffice_path)
    return results[0] if results else False


def main():
    parser = argparse.ArgumentParser(description="PPT 演示文稿转 PDF 工具（PowerPoint COM）")
    parser.add_argument("inputs", nargs="+", help="文件路径、目录或通配符（支持多个）")
    parser.add_argument("--output", "-o", help="输出目录或单文件输出路径 (默认: %(default)s)",
                        default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--names", nargs="+", help="依次指定每个输入文件对应的输出PDF文件名")
    parser.add_argument("--force", action="store_true",
                        help="强制重新转换，忽略缓存")
    add_engine_arguments(parser, "office")
    args = parser.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout 必须为正整数")
    try:
        args.engine = resolve_engine(args.engine, "ppt", args.libreoffice_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"转换引擎: {args.engine}")

    # 收集文件
    files = collect_files(args.inputs)
    if not files:
        print("❌ 未找到任何 PPT 文件")
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
