#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 转图片工具（带缓存检查）

将 PDF 每页转为图片，输出到统一目录。
自动计算确定性文件夹名（基于源文件完整路径），并在转换前检查缓存。
支持自动 DPI 计算（根据 PDF 页面尺寸，让长边尽量吃满目标像素数）。
支持多文件输入。

用法:
    python pdf2img.py "D:\\path\\to\\file.pdf"              # 默认: auto 1500px + JPG q85
    python pdf2img.py "file1.pdf" "file2.pdf"              # 多文件输入
    python pdf2img.py "D:\\path\\to\\file.pdf" -q 60        # 降低质量以减小体积
    python pdf2img.py "D:\\path\\to\\file.pdf" --target 1200 # 降低目标分辨率
    python pdf2img.py "D:\\path\\to\\file.pdf" --density 150 # 手动指定 DPI（禁用 auto）
    python pdf2img.py "D:\\path\\to\\file.pdf" -f png        # 输出 PNG 格式
    python pdf2img.py "D:\\path\\to\\file.pdf" --force       # 忽略缓存强制重转
    python pdf2img.py "D:\\path\\to\\file.pdf" --pages 30-40           # 只转换第30-40页（PDF物理页码）
    python pdf2img.py "D:\\path\\to\\file.pdf" --pages 25              # 只转换第25页
    python pdf2img.py "D:\\path\\to\\file.pdf" --pages 11-14,31-39    # 多段页码范围
    python pdf2img.py "D:\\path\\to\\file.pdf" --pages 11-14,25,31-39 # 混合：范围+单页

依赖:
    ImageMagick (magick 命令) + Ghostscript
"""

import sys
import re
import argparse
import subprocess
import math
import os
from pathlib import Path

# 默认配置
DEFAULT_OUTPUT_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[2] / ".local"))) / "pdf-images"
DEFAULT_DENSITY = 150
DEFAULT_TARGET_PX = 1500  # 自动模式下长边目标像素数（Claude 推荐上限 1568）
DEFAULT_FORMAT = "jpg"
DEFAULT_QUALITY = 85
SIZE_LIMIT_MB = 32  # Claude API 单次对话图片总大小上限
MAGICK_CMD = "magick"
STITCHER_SCRIPT = Path(__file__).resolve().parents[1] / "images" / "image_stitcher.py"


def parse_pages(pages_str: str) -> list[tuple[int, int]]:
    """解析页码规格字符串为 (start, end) 元组列表。

    支持: '25', '30-40', '11-14,31-39', '11-14,25,31-39'
    """
    segments = []
    for part in pages_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            s, e = part.split('-', 1)
            s, e = int(s), int(e)
        else:
            s = e = int(part)
        if s < 1 or e < s:
            raise ValueError(f"无效的页码段: '{part}'")
        segments.append((s, e))
    if not segments:
        raise ValueError("页码规格为空")
    return segments


def get_all_pages(segments: list[tuple[int, int]]) -> list[int]:
    """从段列表获取所有页码的排序去重列表。"""
    pages = set()
    for s, e in segments:
        pages.update(range(s, e + 1))
    return sorted(pages)


def format_pages_desc(segments: list[tuple[int, int]]) -> str:
    """将段列表格式化为可读描述，如 '11-14, 25, 31-39'。"""
    return ", ".join(str(s) if s == e else f"{s}-{e}" for s, e in segments)


def convert_single_range(pdf_path: Path, target_dir: Path, page_start: int, page_end: int,
                         density: int, fmt: str, ext: str, quality: int) -> int:
    """转换 PDF 的单个页码范围，返回转换的页数。异常向上抛出。"""
    output_pattern = str(target_dir / f"_tmp_%d.{ext}")
    pdf_input = f"{pdf_path}[{page_start - 1}-{page_end - 1}]"
    cmd = [
        MAGICK_CMD, "-density", str(density), pdf_input,
        "-background", "white", "-alpha", "remove", "-alpha", "off",
    ]
    if fmt == "jpg":
        cmd.extend(["-quality", str(quality)])
    cmd.append(output_pattern)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"❌ 转换失败 (页码 {page_start}-{page_end}): {result.stderr}")
        return 0

    # ImageMagick 对 pdf[start-end] 范围语法，输出编号保持原始页码偏移
    # 例如 pdf[26-28] → _tmp_26.jpg, _tmp_27.jpg, _tmp_28.jpg
    converted = 0
    for i in range(page_start - 1, page_end):
        src = target_dir / f"_tmp_{i}.{ext}"
        dst = target_dir / f"{i + 1}.{ext}"
        if src.exists():
            src.rename(dst)
            converted += 1
    return converted


def sanitize_path_component(name: str) -> str:
    """清理路径组件中的不安全字符，使其适合作为 Windows 文件夹/文件名。

    规则：
    1. 去除控制字符（ASCII 0-31）
    2. 去除 Windows 文件名禁用字符（<>:"/\\|?*）
    3. 连续空白字符合并为单个空格
    4. 去除首尾空格和末尾点号（Windows 会静默吞掉末尾的 . 和空格）
    5. Windows 保留设备名（CON, NUL, COM1 等）加前缀避免冲突
    6. 空结果替换为 '_'
    """
    # 控制字符 + Windows 禁用字符
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '', name)
    # 连续空白合并
    name = re.sub(r'\s+', ' ', name)
    # 去除首尾空格和末尾点号
    name = name.strip().rstrip('.')
    # 空结果
    if not name:
        return '_'
    # Windows 保留设备名（不区分大小写，可能带扩展名如 CON.txt）
    _RESERVED = {'CON', 'PRN', 'AUX', 'NUL',
                 *(f'COM{i}' for i in range(1, 10)),
                 *(f'LPT{i}' for i in range(1, 10))}
    if name.split('.')[0].upper() in _RESERVED:
        name = f'_{name}'
    return name


def path_to_folder_name(file_path: Path) -> str:
    """将文件完整路径转换为确定性的文件夹名（去盘符、去扩展名、路径分隔符→下划线）。

    对每个路径组件做字符清理，确保生成的文件夹名在 Windows 上安全。
    """
    parts = file_path.resolve().with_suffix('').parts[1:]
    sanitized = [sanitize_path_component(p) for p in parts]
    return "_".join(sanitized)


def get_pdf_page_size(pdf_path: Path) -> tuple[float, float]:
    """获取 PDF 第一页的物理尺寸（英寸）。
    
    通过 72 DPI 渲染获取像素数，再除以 72 得到英寸。
    PDF 标准：1 point = 1/72 inch，所以 72 DPI 下像素数 = point 数。
    """
    cmd = [
        MAGICK_CMD, "identify", "-density", "72",
        "-format", "%w %h", f"{pdf_path}[0]"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None, None
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            width_pt = float(parts[0])
            height_pt = float(parts[1])
            return width_pt / 72.0, height_pt / 72.0  # 转为英寸
    except Exception:
        pass
    return None, None


def calc_optimal_dpi(pdf_path: Path, target_px: int) -> int:
    """根据 PDF 页面尺寸和目标像素数，计算最优 DPI。
    
    公式: DPI = target_px / max(width_inch, height_inch)
    """
    w_inch, h_inch = get_pdf_page_size(pdf_path)
    if w_inch is None or h_inch is None:
        print(f"⚠️ 无法读取 PDF 页面尺寸，回退到默认 DPI={DEFAULT_DENSITY}")
        return DEFAULT_DENSITY
    
    long_edge_inch = max(w_inch, h_inch)
    optimal_dpi = math.floor(target_px / long_edge_inch)
    
    # 限制范围：最低 72，最高 600
    optimal_dpi = max(72, min(600, optimal_dpi))
    
    print(f"📐 页面尺寸: {w_inch:.1f} × {h_inch:.1f} 英寸")
    print(f"📁 目标长边: {target_px}px → 计算 DPI = {optimal_dpi}")
    
    # 验证实际输出像素
    actual_long = int(long_edge_inch * optimal_dpi)
    actual_short = int(min(w_inch, h_inch) * optimal_dpi)
    print(f"📏 预计输出: {actual_long} × {actual_short} px")
    
    return optimal_dpi


def process_single_pdf(pdf_path: Path, args, page_segments=None, all_pages=None, name_override=None) -> bool:
    """处理单个 PDF 文件的转换。返回 True 表示成功。"""

    # 确定 DPI
    if args.density is not None:
        density = args.density
    elif not args.no_auto:
        density = calc_optimal_dpi(pdf_path, args.target)
    else:
        density = DEFAULT_DENSITY

    fmt = args.format
    ext = fmt if fmt == "png" else "jpg"

    # 计算目标文件夹
    out_root = Path(args.output)
    if name_override:
        folder_name = sanitize_path_component(name_override)
    else:
        folder_name = path_to_folder_name(pdf_path)
    target_dir = out_root / folder_name

    print(f"📄 源文件: {pdf_path}")
    print(f"📁 目标: {target_dir}")
    page_info = f", pages={format_pages_desc(page_segments)}" if page_segments else ""
    print(f"⚙️ 参数: density={density}, format={fmt}" + 
          (f", quality={args.quality}" if fmt == "jpg" else "") + page_info)

    # 缓存检查（兼容 png 和 jpg）
    cached = False
    img_count = 0
    if not args.force and target_dir.exists():
        if all_pages:
            # 按页码检查缓存
            all_exist = all((target_dir / f"{p}.{ext}").exists() for p in all_pages)
            if all_exist:
                cached = True
                img_count = len(all_pages)
                print(f"⏭️ 已缓存 ({img_count} 张 {ext} 图片, 页码 {format_pages_desc(page_segments)})，跳过转换")
                print(f"   路径: {target_dir}")
        else:
            cached_files = list(target_dir.glob(f"*.{ext}"))
            if cached_files:
                cached = True
                img_count = len(cached_files)
                print(f"⏭️ 已缓存 ({img_count} 张 {ext} 图片)，跳过转换")
                print(f"   路径: {target_dir}")

    if not cached:
        # 创建目录
        target_dir.mkdir(parents=True, exist_ok=True)

        if args.force:
            import time
            previous = target_dir / "previous" / str(time.time_ns())
            old_files = [target_dir / f"{p}.{ext}" for p in all_pages] if all_pages else list(target_dir.glob(f"*.{ext}"))
            for old in old_files:
                if old.exists():
                    previous.mkdir(parents=True, exist_ok=True)
                    old.rename(previous / old.name)

        # 转换
        try:
            if page_segments:
                # 多段模式：逐段转换
                img_count = 0
                for seg_start, seg_end in page_segments:
                    seg_desc = f"{seg_start}" if seg_start == seg_end else f"{seg_start}-{seg_end}"
                    seg_count = seg_end - seg_start + 1
                    print(f"🔄 正在转换页码 {seg_desc} ({seg_count} 页)...")
                    converted = convert_single_range(
                        pdf_path, target_dir, seg_start, seg_end,
                        density, fmt, ext, args.quality
                    )
                    if converted == 0:
                        return False
                    img_count += converted
                print(f"✅ 转换完成! 共 {img_count} 张 {ext} 图片（页码 {format_pages_desc(page_segments)}）")
            else:
                # 全量模式
                output_pattern = str(target_dir / f"%d.{ext}")
                cmd = [
                    MAGICK_CMD, "-density", str(density), str(pdf_path),
                    "-background", "white", "-alpha", "remove", "-alpha", "off",
                ]
                if fmt == "jpg":
                    cmd.extend(["-quality", str(args.quality)])
                cmd.append(output_pattern)
                print(f"🔄 正在转换...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if result.returncode != 0:
                    print(f"❌ 转换失败: {result.stderr}")
                    return False
                img_files = sorted(target_dir.glob(f"*.{ext}"), key=lambda f: int(f.stem), reverse=True)
                for f in img_files:
                    f.rename(f.with_name(f"{int(f.stem) + 1}.{ext}"))
                img_count = len(img_files)
                print(f"✅ 转换完成! {img_count} 张 {ext} 图片（编号 1~{img_count}）")
        except FileNotFoundError:
            print(f"❌ 找不到 magick 命令，请确认 ImageMagick 已安装并在 PATH 中")
            return False
        except subprocess.TimeoutExpired:
            print(f"❌ 转换超时 (600s)")
            return False

        # 统计总大小
        total_bytes = sum(f.stat().st_size for f in target_dir.glob(f"*.{ext}"))
        total_mb = total_bytes / (1024 * 1024)
        print(f"   路径: {target_dir}")
        print(f"   总大小: {total_mb:.1f} MB（平均 {total_bytes/img_count/1024:.0f} KB/页）")

        # 超限提示
        if total_mb > SIZE_LIMIT_MB:
            print(f"")
            print(f"⚠️ 总大小 {total_mb:.1f} MB 超过 Claude {SIZE_LIMIT_MB}MB 上限！")
            print(f"   建议降低质量: --quality 60 (当前 {args.quality})")
            print(f"   或降低分辨率: --target 1200 (当前 {args.target})")
            print(f"   示例: python pdf2img.py \"{pdf_path}\" --quality 60 --force")
        elif total_mb > SIZE_LIMIT_MB * 0.8:
            print(f"")
            print(f"💡 总大小 {total_mb:.1f} MB，接近 {SIZE_LIMIT_MB}MB 上限，留意空间")

    # 拼接逻辑：默认 ≥2 页自动拼接，--no-stitch 禁用，--stitch 手动指定 preset
    no_stitch = getattr(args, 'no_stitch', False)
    if args.stitch:
        stitch_preset = args.stitch
        do_stitch = True
    elif not no_stitch and img_count >= 2:
        stitch_preset = "4"
        do_stitch = True
    else:
        do_stitch = False

    if do_stitch:
        print(f"")
        print(f"🔗 自动拼接（preset={stitch_preset}, {img_count} 张图片）...")
        stitch_cmd = [
            sys.executable, str(STITCHER_SCRIPT),
            "-i", str(target_dir),
            "--preset", stitch_preset,
            "--auto-size",
            "--no-label",
            "--format", "jpg",
            "-p", sanitize_path_component(pdf_path.stem),
        ]
        try:
            result = subprocess.run(stitch_cmd, timeout=120)
            if result.returncode != 0:
                print(f"⚠️ 拼接过程出错")
        except Exception as e:
            print(f"⚠️ 拼接失败: {e}")
    elif img_count == 1:
        print(f"\n📌 仅 1 页，跳过拼接")

    return True


def main():
    parser = argparse.ArgumentParser(description="PDF 转图片工具（带缓存检查，支持自动 DPI）")
    parser.add_argument("pdf", nargs="+", help="PDF 文件路径（支持多个文件）")
    parser.add_argument("--names", nargs="+", help="依次指定每个 PDF 对应的输出图片子目录名")
    parser.add_argument("--density", type=int, default=None,
                        help=f"DPI 设置（手动指定，与 --auto 互斥）")
    parser.add_argument("--no-auto", action="store_true",
                        help="禁用自动 DPI 计算（默认开启 auto）")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_PX,
                        help=f"自动模式的目标长边像素数 (默认 {DEFAULT_TARGET_PX})")
    parser.add_argument("--format", "-f", choices=["png", "jpg"], default=DEFAULT_FORMAT,
                        help=f"输出格式 (默认 {DEFAULT_FORMAT})")
    parser.add_argument("--quality", "-q", type=int, default=DEFAULT_QUALITY,
                        help=f"JPG 质量 1-100 (默认 {DEFAULT_QUALITY}，仅 jpg 格式生效)")
    parser.add_argument("--output", "-o", help="输出根目录 (默认: %(default)s)",
                        default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--force", action="store_true",
                        help="强制重新转换，忽略缓存")
    parser.add_argument("--stitch", nargs="?", const="4", default=None,
                        choices=["4", "6"],
                        help="转换后自动拼接（可选 preset: 4=每页4张, 6=每页6张, 默认 4）")
    parser.add_argument("--no-stitch", action="store_true",
                        help="禁用自动拼接（默认 ≥2 页自动拼接）")
    parser.add_argument("--pages", type=str, default=None,
                        help="指定页码范围（PDF物理页码，从1开始）。"
                             "格式: '25'（单页）, '30-40'（范围）, '11-14,31-39'（多段）, "
                             "'11-14,25,31-39'（混合）。注意：多文件时页码范围应用于所有文件")
    args = parser.parse_args()

    # 解析页码范围
    page_segments = None  # list of (start, end) tuples
    all_pages = None      # sorted list of all page numbers
    if args.pages:
        try:
            page_segments = parse_pages(args.pages)
            all_pages = get_all_pages(page_segments)
        except (ValueError, TypeError) as ex:
            print(f"页码格式错误: {ex}")
            sys.exit(1)

    # 收集并验证所有 PDF 文件
    pdf_paths = []
    for item in args.pdf:
        p = Path(item).resolve()
        if p.is_dir():
            # 目录模式：收集目录下所有 PDF
            found = sorted(p.glob("*.pdf"))
            if not found:
                print(f"⚠️ 目录中无 PDF 文件: {p}")
            pdf_paths.extend(found)
        elif p.is_file():
            if p.suffix.lower() != ".pdf":
                print(f"⚠️ 跳过非 PDF 文件: {p.name}")
            else:
                pdf_paths.append(p)
        else:
            print(f"❌ 路径不存在: {p}")

    if not pdf_paths:
        print("未找到任何 PDF 文件")
        sys.exit(1)

    if args.names and len(args.names) != len(pdf_paths):
        print(f"❌ 错误: 指定的输出名称数量 ({len(args.names)}) 与输入文件数量 ({len(pdf_paths)}) 不一致！")
        sys.exit(1)

    # 单文件：直接处理（保持原有简洁输出风格）
    if len(pdf_paths) == 1:
        name_override = args.names[0] if args.names else None
        ok = process_single_pdf(pdf_paths[0], args, page_segments, all_pages, name_override)
        sys.exit(0 if ok else 1)

    # 多文件：带序号和统计
    if args.pages:
        print(f"⚠️ 注意：--pages 参数将应用于所有 {len(pdf_paths)} 个文件")

    print(f"📋 共 {len(pdf_paths)} 个 PDF 文件待处理")

    success = 0
    for idx, pdf_path in enumerate(pdf_paths, 1):
        print(f"\n{'='*50}")
        print(f"[{idx}/{len(pdf_paths)}] 📄 {pdf_path.name}")
        name_override = args.names[idx - 1] if args.names else None
        if process_single_pdf(pdf_path, args, page_segments, all_pages, name_override):
            success += 1

    print(f"\n{'='*50}")
    print(f"📊 结果: {success}/{len(pdf_paths)} 成功")
    sys.exit(0 if success == len(pdf_paths) else 1)


if __name__ == "__main__":
    main()
