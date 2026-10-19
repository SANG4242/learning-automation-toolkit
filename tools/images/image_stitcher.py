"""
图片拼接命令行工具
将多张图片拼接成网格布局的大图，方便AI一次性查看多张图片
每张图片下方显示名称标签

================================================================================
【设计背景】
将多页资料合成概览图，便于先了解结构，再按需查看原图。
预设输出约2K像素，实际上传显示尺寸取决于模型与宿主。
文字、公式和细节需要查看成图后判断，必要时读取单页。

【预设说明】
- 6张预设（默认）: 2列×3行，每页6张，平衡数量与清晰度
- 4张预设: 2列×2行，每页4张，更高清晰度，适合复杂电路图

【筛选功能】
- --select: 按序号选择图片，支持范围和逗号分隔（如 7-9,24 表示第7、8、9、24张）
- --filter: 按文件名通配符匹配（如 "*等价类*" 匹配包含"等价类"的文件）
- --files:  直接指定文件名（逗号分隔），支持模糊匹配（可省略扩展名和序号前缀）
================================================================================

使用方法:
    # 使用默认6张预设
    python image_stitcher.py -i "图片目录路径"
    
    # 使用4张预设（更清晰）
    python image_stitcher.py -i "图片目录路径" --preset 4
    
    # 选择特定图片（按序号）
    python image_stitcher.py -i "图片目录路径" --select 7-9,24
    
    # 选择特定图片（按文件名匹配）
    python image_stitcher.py -i "图片目录路径" --filter "*等价类*"
    
    # 直接指定文件名
    python image_stitcher.py -i "图片目录路径" --files "等价类示例图_R1,最大元最小元示例图"
    
    # 自定义参数
    python image_stitcher.py -i "图片目录路径" -p "输出前缀" --theme dark
    
更多帮助:
    python image_stitcher.py --help
"""

from PIL import Image, ImageDraw, ImageFont
import os
import glob
import argparse
import fnmatch
import re

# 主题预设
THEMES = {
    'light': {
        'bg': (255, 255, 255),       # 白色背景
        'label_bg': (240, 240, 240), # 浅灰标签背景
        'text': (33, 33, 33)         # 黑色文字
    },
    'dark': {
        'bg': (26, 26, 46),          # 深色背景
        'label_bg': (22, 33, 62),    # 深色标签背景
        'text': (200, 200, 200)      # 浅色文字
    }
}

# 布局预设 - 针对AI上传优化（目标2K分辨率，上传后压缩到1K仍清晰）
# 计算公式：width = cols * cell_width + (cols + 1) * padding
#          height = rows * (cell_height + label_height) + (rows + 1) * padding
PRESETS = {
    '6': {  # 6张预设（默认）- 平衡数量与清晰度
        'cols': 2,
        'rows': 3,
        'cell_width': 1000,
        'cell_height': 620,
        'padding': 20,
        'font_size': 36,
        'label_height': 50,
        # 输出尺寸: 2*1000 + 3*20 = 2060 宽
        #          3*(620+50) + 4*20 = 2090 高
    },
    '4': {  # 4张预设 - 更高清晰度，适合复杂电路图
        'cols': 2,
        'rows': 2,
        'cell_width': 1000,
        'cell_height': 950,
        'padding': 20,
        'font_size': 36,
        'label_height': 50,
        # 输出尺寸: 2*1000 + 3*20 = 2060 宽
        #          2*(950+50) + 3*20 = 2060 高
    }
}


def calc_auto_cell_height(images, cell_width):
    """根据第一张图片的实际宽高比，计算与 cell_width 匹配的 cell_height。
    
    这样格子比例与源图一致，不产生横向空白。
    """
    for img_path in images:
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                if w > 0 and h > 0:
                    ratio = h / w  # 高宽比
                    cell_height = int(cell_width * ratio)
                    print(f"📐 源图尺寸: {w}×{h}px，宽高比 1:{ratio:.3f}")
                    print(f"🔧 自动计算 cell_height = {cell_width} × {ratio:.3f} = {cell_height}px")
                    return cell_height
        except Exception:
            continue
    return None

def get_sorted_images(folder):
    """获取并按编号排序的图片列表"""
    patterns = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.webp']
    images = []
    for pattern in patterns:
        images.extend(glob.glob(os.path.join(folder, pattern)))
    
    # 按文件名中的数字排序
    def extract_number(path):
        basename = os.path.basename(path)
        # 提取开头的数字
        num_str = ''
        for char in basename:
            if char.isdigit():
                num_str += char
            else:
                break
        return int(num_str) if num_str else 999
    
    images.sort(key=extract_number)
    return images


def parse_select_string(select_str):
    """
    解析选择字符串，返回选中的序号列表（1-indexed）
    
    参数:
        select_str: 选择字符串，支持以下格式:
            - 单个数字: "7" -> [7]
            - 逗号分隔: "7,9,24" -> [7, 9, 24]
            - 范围: "7-9" -> [7, 8, 9]
            - 混合: "7-9,24,30-32" -> [7, 8, 9, 24, 30, 31, 32]
    
    返回:
        排序后的序号列表（1-indexed）
    """
    if not select_str:
        return []
    
    result = set()
    parts = select_str.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if '-' in part:
            # 处理范围，如 "7-9"
            match = re.match(r'^(\d+)-(\d+)$', part)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                if start <= end:
                    result.update(range(start, end + 1))
                else:
                    print(f" 警告: 无效的范围 '{part}'，起始值应小于等于结束值")
            else:
                print(f" 警告: 无法解析 '{part}'")
        else:
            # 处理单个数字
            if part.isdigit():
                result.add(int(part))
            else:
                print(f" 警告: 无法解析 '{part}'")
    
    return sorted(result)


def filter_images_by_select(images, select_indices):
    """
    按序号筛选图片（1-indexed）
    
    参数:
        images: 图片路径列表
        select_indices: 要选择的序号列表（1-indexed）
    
    返回:
        筛选后的图片路径列表
    """
    result = []
    for idx in select_indices:
        if 1 <= idx <= len(images):
            result.append(images[idx - 1])
        else:
            print(f" 警告: 序号 {idx} 超出范围 (1-{len(images)})")
    return result


def filter_images_by_pattern(images, pattern):
    """
    按文件名通配符模式筛选图片
    
    参数:
        images: 图片路径列表
        pattern: 通配符模式（如 "*等价类*"）
    
    返回:
        匹配的图片路径列表
    """
    result = []
    for img_path in images:
        basename = os.path.basename(img_path)
        if fnmatch.fnmatch(basename, pattern):
            result.append(img_path)
    return result


def normalize_filename(filename):
    """
    标准化文件名，用于模糊匹配
    
    处理规则:
        1. 移除扩展名
        2. 移除开头的数字序号和下划线（如 "07_" -> ""）
        3. 转为小写
    
    参数:
        filename: 原始文件名
    
    返回:
        标准化后的文件名
    """
    # 移除扩展名
    name = os.path.splitext(filename)[0]
    # 移除开头的数字序号和下划线/分隔符
    name = re.sub(r'^\d+[_\-\.\s]*', '', name)
    # 转为小写
    return name.lower()


def filter_images_by_names(images, names_str):
    """
    按文件名列表筛选图片（支持模糊匹配）
    
    匹配规则（按优先级）:
        1. 完全匹配（包含扩展名）
        2. 不含扩展名的完全匹配
        3. 忽略序号前缀的匹配
        4. 包含关系匹配（输入是文件名的子串）
    
    参数:
        images: 图片路径列表
        names_str: 逗号分隔的文件名列表
    
    返回:
        匹配的图片路径列表（保持输入顺序）
    """
    # 解析输入的文件名列表
    target_names = [name.strip() for name in names_str.split(',') if name.strip()]
    if not target_names:
        return []
    
    # 构建图片信息索引
    img_info = []
    for img_path in images:
        basename = os.path.basename(img_path)
        name_no_ext = os.path.splitext(basename)[0]
        normalized = normalize_filename(basename)
        img_info.append({
            'path': img_path,
            'basename': basename,
            'name_no_ext': name_no_ext,
            'normalized': normalized
        })
    
    result = []
    matched_paths = set()  # 避免重复
    
    for target in target_names:
        target_lower = target.lower()
        target_no_ext = os.path.splitext(target)[0].lower()
        target_normalized = normalize_filename(target)
        
        found = False
        
        # 优先级1: 完全匹配（包含扩展名）
        for info in img_info:
            if info['basename'].lower() == target_lower:
                if info['path'] not in matched_paths:
                    result.append(info['path'])
                    matched_paths.add(info['path'])
                    found = True
                    break
        
        if found:
            continue
        
        # 优先级2: 不含扩展名的完全匹配
        for info in img_info:
            if info['name_no_ext'].lower() == target_no_ext:
                if info['path'] not in matched_paths:
                    result.append(info['path'])
                    matched_paths.add(info['path'])
                    found = True
                    break
        
        if found:
            continue
        
        # 优先级3: 忽略序号前缀的匹配
        for info in img_info:
            if info['normalized'] == target_normalized:
                if info['path'] not in matched_paths:
                    result.append(info['path'])
                    matched_paths.add(info['path'])
                    found = True
                    break
        
        if found:
            continue
        
        # 优先级4: 包含关系匹配
        for info in img_info:
            if target_lower in info['name_no_ext'].lower():
                if info['path'] not in matched_paths:
                    result.append(info['path'])
                    matched_paths.add(info['path'])
                    found = True
                    break
        
        if not found:
            print(f" 警告: 未找到匹配 '{target}' 的图片")
    
    return result

def get_font(size):
    """获取字体，优先使用微软雅黑"""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",    # 黑体
        "C:/Windows/Fonts/simsun.ttc",    # 宋体
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                pass
    return ImageFont.load_default()

def resize_image_to_fit(img, max_width, max_height):
    """等比例缩放图片以填满指定区域（保持比例）"""
    width_ratio = max_width / img.width
    height_ratio = max_height / img.height
    ratio = min(width_ratio, height_ratio)
    
    new_width = int(img.width * ratio)
    new_height = int(img.height * ratio)
    
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

def create_combined_image(image_paths, output_path, config):
    """将多张图片拼接成一张大图"""
    if not image_paths:
        return
    
    # 解包配置
    cols = config['cols']
    rows = config['rows']
    cell_width = config['cell_width']
    cell_height = config['cell_height']
    padding = config['padding']
    label_height = config['label_height'] if config['show_label'] else 0
    font_size = config['font_size']
    theme = THEMES[config['theme']]
    show_label = config['show_label']
    
    # 加载所有图片
    images = [Image.open(p) for p in image_paths]
    names = [os.path.splitext(os.path.basename(p))[0] for p in image_paths]
    
    # 计算实际需要的行数（可能最后一页不满）
    actual_count = len(images)
    actual_rows = (actual_count + cols - 1) // cols
    
    # 计算总画布大小
    total_cell_height = cell_height + label_height
    canvas_width = cols * cell_width + (cols + 1) * padding
    canvas_height = actual_rows * total_cell_height + (actual_rows + 1) * padding
    
    # 创建画布
    canvas = Image.new('RGB', (canvas_width, canvas_height), theme['bg'])
    draw = ImageDraw.Draw(canvas)
    font = get_font(font_size)
    
    # 粘贴图片
    for idx, (img, name) in enumerate(zip(images, names)):
        row = idx // cols
        col = idx % cols
        
        # 计算单元格左上角位置
        cell_x = padding + col * (cell_width + padding)
        cell_y = padding + row * (total_cell_height + padding)
        
        # 如果图片有透明通道，转换为RGB
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, theme['bg'])
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 缩放图片以填满单元格
        resized_img = resize_image_to_fit(img, cell_width, cell_height)
        
        # 图片居中位置
        img_x = cell_x + (cell_width - resized_img.width) // 2
        img_y = cell_y + (cell_height - resized_img.height) // 2
        
        # 粘贴图片
        canvas.paste(resized_img, (img_x, img_y))
        
        # 绘制标签
        if show_label:
            label_y = cell_y + cell_height
            draw.rectangle([cell_x, label_y, cell_x + cell_width, label_y + label_height], 
                          fill=theme['label_bg'])
            
            # 绘制文字（居中）
            bbox = draw.textbbox((0, 0), name, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = cell_x + (cell_width - text_width) // 2
            text_y = label_y + (label_height - text_height) // 2
            draw.text((text_x, text_y), name, fill=theme['text'], font=font)
        
        resized_img.close()
    
    # 保存
    ext = os.path.splitext(output_path)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        canvas.save(output_path, 'JPEG', quality=config.get('quality', 85))
    else:
        canvas.save(output_path, 'PNG')
    file_size = os.path.getsize(output_path)
    size_str = f"{file_size / 1024:.0f}KB" if file_size < 1024 * 1024 else f"{file_size / 1024 / 1024:.1f}MB"
    print(f"✅ 已生成: {output_path} ({size_str})")
    
    # 关闭原始图片
    for img in images:
        img.close()

def main():
    # 获取默认预设值
    default_preset = PRESETS['6']
    
    parser = argparse.ArgumentParser(
        description='图片拼接工具 - 将多张图片拼接成网格布局（针对AI上传优化）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
预设说明:
  --preset 6  : 2列×3行，每页6张（默认，平衡数量与清晰度）
  --preset 4  : 2列×2行，每页4张（更高清晰度，适合复杂电路图）

筛选功能:
  --select    : 按序号选择图片（1-indexed），支持范围和逗号分隔
  --filter    : 按文件名通配符匹配
  --files     : 直接指定文件名（逗号分隔），支持模糊匹配

示例:
  # 使用默认6张预设
  python image_stitcher.py -i "d:\\课件\\第10章.assets"
  
  # 使用4张预设（更清晰）
  python image_stitcher.py -i "d:\\课件\\第10章.assets" --preset 4
  
  # 选择第7-9张和第24张图片
  python image_stitcher.py -i "d:\\课件" --select 7-9,24
  
  # 选择文件名包含"等价类"的图片
  python image_stitcher.py -i "d:\\课件" --filter "*等价类*"
  
  # 直接指定文件名（支持模糊匹配，可省略序号前缀和扩展名）
  python image_stitcher.py -i "d:\\课件" --files "等价类示例图_R1,最大元最小元示例图"
  
  # 自定义前缀和主题
  python image_stitcher.py -i "d:\\图片" -p "第10章_运算器" --theme dark
  
  # 手动覆盖预设参数
  python image_stitcher.py -i "d:\\图片" --preset 6 --font-size 40
        '''
    )
    
    parser.add_argument('-i', '--input', 
                        default='.', 
                        help='输入图片目录路径 (默认: 当前目录)')
    parser.add_argument('-o', '--output', 
                        default=None, 
                        help='输出目录路径 (默认: 输入目录下的"拼接结果"子目录)')
    parser.add_argument('-p', '--prefix', 
                        default='拼接图片', 
                        help='输出文件名前缀 (默认: 拼接图片)')
    parser.add_argument('--preset', 
                        choices=['4', '6'], default='6',
                        help='布局预设: 4=每页4张(更清晰), 6=每页6张(默认)')
    parser.add_argument('--auto-size', action='store_true',
                        help='根据源图实际宽高比自动计算 cell_height，消除横向空白（推荐用于PDF转图片）')
    parser.add_argument('-c', '--cols', 
                        type=int, default=None, 
                        help=f'每行列数 (默认: 使用预设值)')
    parser.add_argument('-r', '--rows', 
                        type=int, default=None, 
                        help=f'每页行数 (默认: 使用预设值)')
    parser.add_argument('-t', '--theme', 
                        choices=['light', 'dark'], default='light', 
                        help='主题配色 (默认: light 白底黑字)')
    parser.add_argument('--cell-width', 
                        type=int, default=None, 
                        help=f'单元格宽度像素 (默认: 使用预设值)')
    parser.add_argument('--cell-height', 
                        type=int, default=None, 
                        help=f'单元格高度像素 (默认: 使用预设值)')
    parser.add_argument('--no-label', 
                        action='store_true', 
                        help='不显示图片名称标签')
    parser.add_argument('--padding', 
                        type=int, default=None, 
                        help=f'图片间距像素 (默认: 使用预设值)')
    parser.add_argument('--font-size', 
                        type=int, default=None, 
                        help=f'标签字体大小 (默认: 使用预设值)')
    parser.add_argument('-s', '--select', 
                        type=str, default=None, 
                        help='按序号选择图片，支持范围和逗号分隔 (如: 7-9,24)')
    parser.add_argument('-f', '--filter', 
                        type=str, default=None, 
                        help='按文件名通配符匹配 (如: "*等价类*")')
    parser.add_argument('--files', 
                        type=str, default=None, 
                        help='直接指定文件名，逗号分隔，支持模糊匹配 (如: "等价类示例图_R1,哈斯图")')
    parser.add_argument('--format', 
                        choices=['png', 'jpg'], default='jpg',
                        help='输出图片格式 (默认: jpg, 体积更小)')
    parser.add_argument('--quality', 
                        type=int, default=85,
                        help='JPG压缩质量 1-100 (默认: 85, 仅format=jpg时有效)')
    
    args = parser.parse_args()
    
    # 应用预设值，命令行参数可覆盖
    preset = PRESETS[args.preset]
    cols = args.cols if args.cols is not None else preset['cols']
    rows = args.rows if args.rows is not None else preset['rows']
    cell_width = args.cell_width if args.cell_width is not None else preset['cell_width']
    cell_height = args.cell_height if args.cell_height is not None else preset['cell_height']
    padding = args.padding if args.padding is not None else preset['padding']
    font_size = args.font_size if args.font_size is not None else preset['font_size']
    label_height = preset['label_height']
    _auto_size_pending = getattr(args, 'auto_size', False)  # 延迟到图片加载后处理

    
    # 验证输入目录
    input_dir = os.path.abspath(args.input)
    if not os.path.isdir(input_dir):
        print(f"❌ 错误: 输入目录不存在: {input_dir}")
        return 1
    
    # 设置输出目录
    if args.output:
        output_dir = os.path.abspath(args.output)
    else:
        output_dir = os.path.join(input_dir, '拼接结果')
    
    # 获取所有图片
    images = get_sorted_images(input_dir)
    
    # 过滤掉输出目录中的图片
    images = [img for img in images if '拼接结果' not in img]
    
    if not images:
        print(f"❌ 错误: 在目录中没有找到图片: {input_dir}")
        return 1
    
    total_images = len(images)
    print(f"📁 输入目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🖼️  找到 {total_images} 张图片")
    
    # --auto-size：根据源图宽高比自动计算 cell_height
    if _auto_size_pending and args.cell_height is None:
        auto_h = calc_auto_cell_height(images, cell_width)
        if auto_h is not None:
            cell_height = auto_h
    
    # 应用筛选条件
    if args.select:
        select_indices = parse_select_string(args.select)
        if not select_indices:
            print(f"❌ 错误: 无法解析选择参数: {args.select}")
            return 1
        images = filter_images_by_select(images, select_indices)
        print(f"🔍 按序号筛选: {args.select} -> 选中 {len(images)} 张")
    
    if args.filter:
        images = filter_images_by_pattern(images, args.filter)
        print(f"🔍 按模式筛选: {args.filter} -> 匹配 {len(images)} 张")
    
    if args.files:
        images = filter_images_by_names(images, args.files)
        print(f"🔍 按文件名筛选: 共匹配 {len(images)} 张")
    
    if not images:
        print(f"❌ 错误: 筛选后没有图片")
        return 1
    
    # 显示选中的图片
    if args.select or args.filter or args.files:
        print(f"📋 选中的图片:")
        for i, img in enumerate(images, 1):
            print(f"   {i}. {os.path.basename(img)}")
    
    print(f" 预设: {args.preset}张/页 ({cols}列 × {rows}行)")
    print(f"📐 单元格: {cell_width}×{cell_height}px, 间距: {padding}px")
    print(f"🎨 主题: {args.theme}")
    print()
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 准备配置
    out_ext = 'jpg' if args.format == 'jpg' else 'png'
    config = {
        'cols': cols,
        'rows': rows,
        'cell_width': cell_width,
        'cell_height': cell_height,
        'padding': padding,
        'label_height': label_height,
        'font_size': font_size,
        'theme': args.theme,
        'show_label': not args.no_label,
        'quality': args.quality
    }
    
    # 计算每页图片数
    images_per_page = cols * rows
    total_pages = (len(images) + images_per_page - 1) // images_per_page
    
    # 缓存检查：预期的拼接结果文件是否全部存在
    expected_files = [
        os.path.join(output_dir, f'{args.prefix}_第{page + 1}页.{out_ext}')
        for page in range(total_pages)
    ]
    if all(os.path.exists(f) for f in expected_files):
        print(f"⏭️ 拼接结果已缓存（{total_pages} 张），跳过拼接")
        print(f"📂 输出目录: {output_dir}")
        return 0
    
    # 分页拼接
    for page in range(total_pages):
        start_idx = page * images_per_page
        end_idx = min(start_idx + images_per_page, len(images))
        page_images = images[start_idx:end_idx]
        
        output_path = os.path.join(output_dir, f'{args.prefix}_第{page + 1}页.{out_ext}')
        create_combined_image(page_images, output_path, config)
    
    print(f"\n🎉 完成！共生成 {total_pages} 张拼接图片")
    print(f"📂 输出目录: {output_dir}")
    return 0

if __name__ == '__main__':
    exit(main())
