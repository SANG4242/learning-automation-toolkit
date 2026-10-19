#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown 图片本地化工具 (Typora 风格)

功能：
1. 扫描指定目录下所有 .md 文件
2. 提取所有在线图片链接 (http/https)
3. 下载图片到 "文件名.assets/" 目录
4. 替换 Markdown 中的链接为本地相对路径

用法：
    python localize_md_images.py <目标目录>
    python localize_md_images.py <目标目录> --dry-run  # 仅统计，不下载

示例：
    python localize_md_images.py "notes"
"""

import os
import re
import sys
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 匹配 Markdown 图片语法: ![alt](url) 或 ![alt](url "title")
MD_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\((https?://[^)\s]+)(?:\s+"[^"]*")?\)')

# 匹配 HTML img 标签: <img src="url" ...>
HTML_IMG_PATTERN = re.compile(r'<img[^>]+src=["\']?(https?://[^"\'>\s]+)["\']?[^>]*>', re.IGNORECASE)


def get_url_extension(url: str) -> str:
    """从 URL 提取文件扩展名"""
    # 移除查询参数
    path = url.split('?')[0]
    ext = os.path.splitext(path)[1].lower()
    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp']:
        return ext
    return '.png'  # 默认 png


def download_image(url: str, save_path: Path, timeout: int = 30) -> bool:
    """下载单张图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"  ❌ 下载失败: {url}\n     错误: {e}")
        return False


def generate_filename(url: str, alt_text: str = "") -> str:
    """生成本地文件名"""
    # 尝试从 URL 提取原始文件名
    path = url.split('?')[0]
    original_name = os.path.basename(path)
    
    # 如果文件名太长或包含特殊字符，用 hash 代替
    if len(original_name) > 50 or not re.match(r'^[\w\-_.]+$', original_name):
        # 使用 URL 的 md5 hash 作为文件名
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        ext = get_url_extension(url)
        return f"image_{url_hash}{ext}"
    
    return original_name


def process_markdown_file(md_path: Path, dry_run: bool = False) -> dict:
    """处理单个 Markdown 文件"""
    result = {
        'file': str(md_path),
        'images_found': 0,
        'images_downloaded': 0,
        'images_failed': 0,
        'already_local': 0,
        'details': []
    }
    
    try:
        content = md_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = md_path.read_text(encoding='gbk')
        except:
            print(f"⚠️ 无法读取文件: {md_path}")
            return result
    
    # 提取所有在线图片
    md_images = MD_IMAGE_PATTERN.findall(content)  # [(alt, url), ...]
    html_images = HTML_IMG_PATTERN.findall(content)  # [url, ...]
    
    # 合并去重
    all_urls = set()
    url_to_alt = {}
    for alt, url in md_images:
        all_urls.add(url)
        url_to_alt[url] = alt
    for url in html_images:
        all_urls.add(url)
        if url not in url_to_alt:
            url_to_alt[url] = ""
    
    result['images_found'] = len(all_urls)
    
    if not all_urls:
        return result
    
    # 创建 .assets 目录
    assets_dir = md_path.parent / f"{md_path.stem}.assets"
    
    if dry_run:
        print(f"📄 {md_path.name}: 发现 {len(all_urls)} 张在线图片")
        for url in list(all_urls)[:3]:  # 只显示前3个
            print(f"   - {url[:80]}...")
        if len(all_urls) > 3:
            print(f"   ... 还有 {len(all_urls) - 3} 张")
        return result
    
    print(f"\n📄 处理: {md_path.name}")
    print(f"   → 保存到: {assets_dir.name}/")
    
    # 下载图片并替换链接
    new_content = content
    for url in all_urls:
        alt = url_to_alt.get(url, "")
        filename = generate_filename(url, alt)
        local_path = assets_dir / filename
        relative_path = f"./{assets_dir.name}/{filename}"
        
        # 下载
        if download_image(url, local_path):
            result['images_downloaded'] += 1
            result['details'].append({'url': url, 'local': str(relative_path), 'status': 'ok'})
            
            # 替换 Markdown 语法
            # 需要处理带 title 和不带 title 的情况
            old_pattern = re.compile(
                r'!\[([^\]]*)\]\(' + re.escape(url) + r'(?:\s+"[^"]*")?\)'
            )
            new_content = old_pattern.sub(f'![\\1]({relative_path})', new_content)
            
            # 替换 HTML 语法
            new_content = new_content.replace(url, relative_path)
            
            print(f"   ✅ {filename}")
        else:
            result['images_failed'] += 1
            result['details'].append({'url': url, 'status': 'failed'})
    
    # 写回文件
    if result['images_downloaded'] > 0:
        md_path.write_text(new_content, encoding='utf-8')
        print(f"   📝 已更新 Markdown 文件")
    
    return result


def scan_directory(target_dir: Path, dry_run: bool = False) -> list:
    """扫描目录下所有 Markdown 文件"""
    md_files = list(target_dir.rglob('*.md'))
    print(f"\n🔍 扫描目录: {target_dir}")
    print(f"📚 发现 {len(md_files)} 个 Markdown 文件\n")
    
    results = []
    for md_file in md_files:
        result = process_markdown_file(md_file, dry_run)
        if result['images_found'] > 0:
            results.append(result)
    
    return results


def print_summary(results: list, dry_run: bool = False):
    """打印统计摘要"""
    total_found = sum(r['images_found'] for r in results)
    total_downloaded = sum(r['images_downloaded'] for r in results)
    total_failed = sum(r['images_failed'] for r in results)
    files_with_images = len(results)
    
    print("\n" + "=" * 50)
    if dry_run:
        print("📊 统计结果 (仅扫描，未下载)")
    else:
        print("📊 处理完成")
    print("=" * 50)
    print(f"  📁 包含在线图片的文件: {files_with_images} 个")
    print(f"  🖼️  在线图片总数: {total_found} 张")
    if not dry_run:
        print(f"  ✅ 下载成功: {total_downloaded} 张")
        print(f"  ❌ 下载失败: {total_failed} 张")
    print("=" * 50)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(1 if len(sys.argv) < 2 else 0)
    
    target_dir = Path(sys.argv[1])
    dry_run = '--dry-run' in sys.argv
    
    if not target_dir.exists():
        print(f"❌ 目录不存在: {target_dir}")
        sys.exit(1)
    
    if dry_run:
        print("🔍 DRY RUN 模式: 仅扫描统计，不下载图片\n")
    
    results = scan_directory(target_dir, dry_run)
    print_summary(results, dry_run)
    
    if dry_run and results:
        print("\n💡 提示: 移除 --dry-run 参数即可开始下载")


if __name__ == '__main__':
    main()
