#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 文档转图片工具（一步到位）

将 docx/doc 经由 docx2pdf.py 转为 PDF，再调用 pdf2img.py 转为图片；默认 Word，可选 WPS/LibreOffice。
两步均复用已有脚本，无重复逻辑。支持单文件、多文件、目录批量转换、通配符筛选。

用法:
    python doc2img.py "文件.docx"
    python doc2img.py "文件1.docx" "文件2.doc"
    python doc2img.py "D:\\某个目录"
    python doc2img.py "D:\\某个目录\\No.9*"            # 通配符筛选
    python doc2img.py "文件.docx" --force
    python doc2img.py "文件.docx" -q 60

输出:
    图片: .local/pdf-images/<路径命名>/1.jpg, 2.jpg, ...
    中间PDF: .local/word-pdf/<路径命名>.pdf（LEARNING_TOOLS_DATA_DIR 可覆盖）

依赖:
    Microsoft Word + PowerShell + pdf2img.py（及其依赖 ImageMagick + Ghostscript）
"""

import sys
import argparse
import subprocess
from pathlib import Path

# 将本脚本所在目录加入 sys.path，以便导入同目录的 docx2pdf
sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx2pdf import (
    WORD_EXTENSIONS,
    collect_files,
    path_to_filename,
    convert_batch,
    add_engine_arguments,
    resolve_engine,
    is_pdf_cached,
)

# 默认配置
from docx2pdf import DEFAULT_OUTPUT_DIR as DEFAULT_PDF_DIR
PDF2IMG_SCRIPT = Path(__file__).resolve().with_name("pdf2img.py")


def pdf_to_images(pdf_path: Path, force: bool, extra_args: list[str]) -> bool:
    """调用 pdf2img.py 完成 PDF→图片转换，所有图片参数由 pdf2img.py 统一管理"""
    cmd = [sys.executable, str(PDF2IMG_SCRIPT), str(pdf_path)]
    if force:
        cmd.append("--force")
    cmd.extend(extra_args)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        # 打印 pdf2img.py 的输出（缩进显示）
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
        if result.returncode != 0:
            for line in result.stderr.strip().split("\n"):
                print(f"  {line}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  ❌ PDF→图片超时 (600s)")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Word 文档转图片工具（一步到位，调用 docx2pdf + pdf2img）"
    )
    parser.add_argument("inputs", nargs="+", help="文件路径、目录或通配符（支持多个）")
    parser.add_argument("--output", "-o", help="指定图片输出目录")
    parser.add_argument("--names", nargs="+", help="依次指定每个输入文件对应的输出图片子目录名")
    parser.add_argument("--force", action="store_true",
                        help="强制重新转换，忽略缓存")
    # 以下参数直接透传给 pdf2img.py
    parser.add_argument("--density", type=int, default=None,
                        help="手动指定 DPI（透传给 pdf2img.py）")
    parser.add_argument("--target", type=int, default=None,
                        help="auto 模式目标长边像素数（透传给 pdf2img.py）")
    parser.add_argument("--format", "-f", choices=["png", "jpg"], default=None,
                        help="输出格式（透传给 pdf2img.py）")
    parser.add_argument("--quality", "-q", type=int, default=None,
                        help="JPG 质量（透传给 pdf2img.py）")
    parser.add_argument("--no-auto", action="store_true",
                        help="禁用自动 DPI（透传给 pdf2img.py）")
    add_engine_arguments(parser, "office")
    args = parser.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout 必须为正整数")
    try:
        args.engine = resolve_engine(args.engine, "word", args.libreoffice_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"转换引擎: {args.engine}")

    # 检查 pdf2img.py 是否存在
    if not PDF2IMG_SCRIPT.exists():
        print(f"❌ 找不到 pdf2img.py: {PDF2IMG_SCRIPT}")
        sys.exit(1)

    # 构建透传参数
    extra_args = []
    if args.density is not None:
        extra_args.extend(["--density", str(args.density)])
    if args.target is not None:
        extra_args.extend(["--target", str(args.target)])
    if args.format is not None:
        extra_args.extend(["--format", args.format])
    if args.quality is not None:
        extra_args.extend(["--quality", str(args.quality)])
    if args.no_auto:
        extra_args.append("--no-auto")

    # 收集文件
    files = collect_files(args.inputs, WORD_EXTENSIONS)
    if not files:
        print("❌ 未找到任何 Word 文件")
        sys.exit(1)

    if args.names and len(args.names) != len(files):
        print(f"❌ 错误: 指定的输出名称数量 ({len(args.names)}) 与输入文件数量 ({len(files)}) 不一致！")
        sys.exit(1)

    print(f"📋 共 {len(files)} 个文件待处理")

    pdf_dir = DEFAULT_PDF_DIR.resolve()
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # 步骤1: 筛选需要 Word→PDF 转换的文件
    all_pairs = []  # [(src, pdf_path), ...]
    to_convert = []  # 需要实际转换的

    for f in files:
        out_name = path_to_filename(f)
        pdf_path = pdf_dir / f"{out_name}.pdf"
        all_pairs.append((f, pdf_path))

        need_convert = args.force or not is_pdf_cached(
            f, pdf_path, args.engine, args.libreoffice_path
        )
        if need_convert:
            to_convert.append((f, pdf_path))
        else:
            print(f"  📄 PDF 已缓存: {f.name}")

    # 批量 Word→PDF
    convert_results = {}
    if to_convert:
        print(f"\n🔄 Word→PDF: {len(to_convert)} 个文件...")
        for src, _ in to_convert:
            print(f"  📝 {src.name}")
        results = convert_batch(to_convert, args.engine, args.timeout, args.libreoffice_path)
        for (src, pdf_path), ok in zip(to_convert, results):
            convert_results[str(src)] = ok
            if ok:
                print(f"  📄 PDF 生成: {pdf_path.name}")

    # 步骤2: PDF→图片
    success = 0
    for idx, (f, pdf_path) in enumerate(all_pairs):
        print(f"\n{'='*50}")
        print(f"📝 处理: {f.name}")

        # 检查 PDF 是否可用
        src_str = str(f)
        if src_str in convert_results and not convert_results[src_str]:
            print(f"  ⚠️ PDF 转换失败，跳过图片生成")
            continue
        if not pdf_path.exists():
            print(f"  ⚠️ PDF 不存在，跳过: {pdf_path}")
            continue

        run_extra_args = list(extra_args)
        if args.output:
            run_extra_args.extend(["--output", args.output])
        if args.names:
            run_extra_args.extend(["--names", args.names[idx]])

        if pdf_to_images(pdf_path, args.force or convert_results.get(src_str, False), run_extra_args):
            success += 1

    print(f"\n{'='*50}")
    print(f"📊 结果: {success}/{len(files)} 成功")
    sys.exit(0 if success == len(files) else 1)


if __name__ == "__main__":
    main()
