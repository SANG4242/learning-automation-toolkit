#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU 全功能客户端 (Full Client)

依托 MinerU 官方 API 实现 PDF/文档/URL 到 Markdown 的高质量转换。
支持本地文件上传、URL直接提取、批量处理、异步查询等全套功能。

基本用法:
    python mineru_pdf2md.py <输入路径或URL>

高级用法:
    python mineru_pdf2md.py <输入> --output <目录> --extra-formats html docx
    python mineru_pdf2md.py <输入> --pages "1-10" --language en
    python mineru_pdf2md.py query <BatchID>  (查询历史任务)

环境变量:
    MINERU_API_TOKEN: MinerU API Token (必需)
"""

import os
import sys
import time
import json
import argparse
import zipfile
import tempfile
import shutil
import requests
import re
from pathlib import Path
from typing import Optional, List, Union

# API 配置
API_BASE_URL = "https://mineru.net/api/v4"
API_TIMEOUT = 60
POLL_INTERVAL = 5
MAX_POLL_TIME = 1800  # 增加到 30 分钟，应对大文件

# 默认 API Token
DEFAULT_API_TOKEN = None

# 文件限制
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
DEFAULT_OUTPUT_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[2] / ".local"))) / "mineru"

class MinerUError(Exception):
    pass

class MinerUClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    
    def _handle_response(self, response: requests.Response, error_msg: str) -> dict:
        """通用响应处理"""
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise MinerUError(f"{error_msg}: 响应非 JSON 格式 (HTTP {response.status_code})")
            
        if response.status_code != 200 or data.get("code") != 0:
            msg = data.get("msg") or data
            raise MinerUError(f"{error_msg}: {msg}")
        return data

    def extract_batch(self, 
                      files_info: List[dict], 
                      model_version: str = "vlm",
                      enable_formula: bool = True,
                      enable_table: bool = True,
                      language: str = "ch",
                      extra_formats: list = None,
                      callback_url: str = None,
                      seed: str = None) -> str:
        """
        提交批量提取任务 (支持 URL 和本地文件混合)
        注意：本地文件需要先调用 apply_upload_urls 上传，此处 files_info 需包含完整信息
        """
        url = f"{API_BASE_URL}/extract/task/batch"
        
        # 构建请求体
        payload = {
            "files": files_info,
            "model_version": model_version,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "language": language
        }
        
        if extra_formats:
            payload["extra_formats"] = extra_formats
        if callback_url:
            payload["callback"] = callback_url
            if seed:
                payload["seed"] = seed
            else:
                payload["seed"] = "trans_agent_default_seed"

        response = requests.post(url, headers=self.headers, json=payload, timeout=API_TIMEOUT)
        data = self._handle_response(response, "提交任务失败")
        return data["data"]["batch_id"]

    def apply_upload_urls(self, filenames: list, model_version: str = "vlm") -> tuple:
        """申请文件上传链接"""
        url = f"{API_BASE_URL}/file-urls/batch"
        payload = {
            "files": [{"name": name} for name in filenames],
            "model_version": model_version
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=API_TIMEOUT)
        data = self._handle_response(response, "申请上传链接失败")
        
        return data["data"]["batch_id"], data["data"]["file_urls"]

    def upload_file(self, upload_url: str, file_path: Path):
        """上传单个文件"""
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            raise MinerUError(f"文件 {file_path.name} 过大 ({file_size/1024/1024:.1f}MB)，限 200MB")
        
        timeout = max(API_TIMEOUT, file_size // (1024 * 1024) * 10 + 60)
        with open(file_path, 'rb') as f:
            requests.put(upload_url, data=f, timeout=timeout) 
            # PUT 上传通常由云厂商直接处理，状态码校验稍微放宽，但一般是 200

    def get_batch_results(self, batch_id: str) -> dict:
        """查询任务进度"""
        url = f"{API_BASE_URL}/extract-results/batch/{batch_id}"
        response = requests.get(url, headers=self.headers, timeout=API_TIMEOUT)
        data = self._handle_response(response, "查询进度失败")
        return data.get("data", {})

    def _sanitize_filename(self, name: str) -> str:
        """清洗文件名，移除 Windows 非法字符"""
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

    def wait_for_batch(self, batch_id: str, target_files: List[str]) -> dict:
        """
        同步等待任务完成
        target_files: 关注的文件名/URL列表，用于判断进度
        """
        start_time = time.time()
        completed_files = set()
        
        print("\n⏳ 任务处理中 (按 Ctrl+C 可中断等待，稍后通过 ID 查询)...")
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > MAX_POLL_TIME:
                raise MinerUError(f"等待超时 ({MAX_POLL_TIME}s)，请稍后使用 query 命令查询")
            
            data = self.get_batch_results(batch_id)
            results = data.get("extract_result", [])
            
            # 统计进度
            all_done = True
            waiting_count = 0
            
            print_lines = []
            
            for res in results:
                raw_name = res.get("file_name") or res.get("url", "未知文件")
                # 只是为了显示，不需要在这里清洗，但在下载时需要
                state = res.get("state")
                
                if state in ["done", "failed"]:
                    completed_files.add(raw_name)
                else:
                    all_done = False
                    waiting_count += 1
                    
                    # 详细进度
                    if state == "running":
                        progress = res.get("extract_progress", {})
                        curr = progress.get("extracted_pages", 0)
                        total = progress.get("total_pages", "?")
                        print_lines.append(f"   > {raw_name}: 解析中 {curr}/{total} 页")
                    elif state == "pending":
                        print_lines.append(f"   > {raw_name}: 排队中...")
                    elif state == "waiting-file":
                        print_lines.append(f"   > {raw_name}: 等待上传...")

            # 只有当有新动态或者每隔几轮才打印，避免刷屏 (这里简单处理：每次都覆盖打印一些简要信息)
            # 为了兼容性，不使用复杂的终端光标控制，只输出关键节点
            
            if all_done:
                print(f"✅ 所有文件处理完毕！耗时 {elapsed:.1f}s")
                return data
            
            # 简报
            sys.stdout.write(f"\r⏱️  已耗时 {elapsed:.0f}s | 剩余 {waiting_count} 个任务正在进行...   ")
            sys.stdout.flush()
            
            time.sleep(POLL_INTERVAL)

    def download_result(self, zip_url: str, output_dir: Path, original_stem: str, fmt_filter: list = None) -> Optional[Path]:
        """下载并解压，适配 Typora 结构"""
        # 清洗文件名
        safe_stem = self._sanitize_filename(original_stem)
        
        try:
            r = requests.get(zip_url, stream=True, timeout=120)
            r.raise_for_status()
            
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                for chunk in r.iter_content(8192):
                    tmp.write(chunk)
                tmp_zip = tmp.name

            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(tmp_zip, 'r') as zf:
                    zf.extractall(tmp_dir)
                
                # 寻找内容
                tmp_path = Path(tmp_dir)
                md_files = list(tmp_path.rglob("*.md"))
                if not md_files: return None
                
                src_md = md_files[0]
                content = src_md.read_text(encoding="utf-8")
                
                # 目标路径
                final_md = output_dir / f"{safe_stem}.md"
                assets_dir = output_dir / f"{safe_stem}.assets"
                
                # 图片处理
                src_imgs = list(tmp_path.rglob("images"))
                if src_imgs and src_imgs[0].is_dir():
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    for img in src_imgs[0].iterdir():
                        shutil.copy2(img, assets_dir)
                    
                    content = content.replace("images/", f"{safe_stem}.assets/")
                    content = content.replace("(images/", f"({safe_stem}.assets/")
                    # 如果文件名含空格，需要对 Markdown 图片路径中的空格做 URL 编码
                    if " " in safe_stem:
                        url_safe = safe_stem.replace(" ", "%20")
                        content = content.replace(f"({safe_stem}.assets/", f"({url_safe}.assets/")
                        content = content.replace(f"![]({safe_stem}.assets/", f"![]({url_safe}.assets/")
                
                final_md.write_text(content, encoding="utf-8")
                
                # 额外格式
                if fmt_filter:
                    for fmt in fmt_filter:
                        for f in tmp_path.rglob(f"*.{fmt}"):
                            shutil.copy2(f, output_dir / f"{safe_stem}.{fmt}")

                return final_md
        except Exception as e:
            print(f"❌ 下载/解压失败: {e}")
            return None
        finally:
            if 'tmp_zip' in locals() and os.path.exists(tmp_zip):
                os.remove(tmp_zip)

def is_url(s: str) -> bool:
    return s.lower().startswith(('http://', 'https://'))

def path_to_folder_name(file_path: Path) -> str:
    """将文件完整路径转换为确定性的文件夹名（去盘符、去扩展名、路径分隔符→下划线）。

    对每个路径组件做字符清理，确保生成的文件夹名在 Windows 上安全。
    """
    def _sanitize_component(name: str) -> str:
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

    parts = file_path.resolve().with_suffix('').parts[1:]
    return "_".join(_sanitize_component(p) for p in parts)

def main():
    parser = argparse.ArgumentParser(description="MinerU 全能文档转换工具")
    
    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="命令模式")
    
    # === 提交命令 (submit) ===
    # 注意：默认行为，如果不输子命令，脚本会尝试把第一个参数当 input 自动进入 submit 模式
    cmd_submit = subparsers.add_parser("submit", help="提交转换任务 (默认)")
    cmd_submit.add_argument("inputs", nargs="+", help="文件路径 或 URL链接")
    # 高级参数
    cmd_submit.add_argument("-o", "--output", help="输出目录")
    cmd_submit.add_argument("-m", "--model", choices=["vlm", "pipeline", "MinerU-HTML"], default="vlm")
    cmd_submit.add_argument("-e", "--extra-formats", nargs="+", choices=["html", "docx", "latex"])
    cmd_submit.add_argument("--pages", help="页码范围 (如 '1-5,10')")
    cmd_submit.add_argument("--language", default="ch", help="OCR语言 (默认 ch, 可选 en 等)")
    cmd_submit.add_argument("--no-wait", action="store_true", help="异步模式：不等待结果，提交后立即退出")
    cmd_submit.add_argument("--no-formula", action="store_true", help="[Pipeline] 关闭公式识别")
    cmd_submit.add_argument("--no-table", action="store_true", help="[Pipeline] 关闭表格识别")
    
    # === 查询命令 (query) ===
    cmd_query = subparsers.add_parser("query", help="查询/下载历史任务")
    cmd_query.add_argument("batch_id", help="任务批次 ID")
    cmd_query.add_argument("-o", "--output", help="输出目录")
    
    # 兼容性处理：如果没提供子命令，默认视为 submit
    # 例如: python script.py d:/test.pdf -> 此时 sys.argv[1] 不是 submit/query
    if len(sys.argv) > 1 and sys.argv[1] not in ['submit', 'query', '-h', '--help']:
        args = parser.parse_args(['submit'] + sys.argv[1:])
    else:
        args = parser.parse_args()
        if not args.command:
            parser.print_help()
            return

    # 初始化配置
    token = os.environ.get("MINERU_API_TOKEN")
    if not token:
        parser.error("请通过 MINERU_API_TOKEN 设置认证信息")
    client = MinerUClient(token)
    
    # 设定输出
    out_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR
    
    # === 处理 提交 逻辑 ===
    if args.command == "submit":
        # 1. 预处理输入，按 (SourceType, ModelVersion) 分组
        # SourceType: 'local' | 'url'
        # ModelVersion: 'vlm' | 'MinerU-HTML' | 'pipeline'
        
        # 默认模型策略:
        # - 用户指定了模型 -> 听用户的 (除了 HTML 文件强制修正)
        # - 用户未指定 -> 
        #    - PDF/Office/Image -> vlm (效果最好)
        #    - HTML/URL(无后缀) -> MinerU-HTML
        
        task_groups = {}  # Key: (source_type, model), Value: list of items
        
        def get_smart_model(filename_or_url, user_model):
            # 提取后缀
            lower_name = filename_or_url.lower()
            # HTML 判定
            if lower_name.endswith('.html') or lower_name.endswith('.htm'):
                return "MinerU-HTML"
            
            # URL 特殊判定: 如果是 URL 且没有明显文档后缀，默认视为网页
            if is_url(filename_or_url):
                # 常见文档后缀
                doc_exts = ('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.png', '.jpg', '.jpeg')
                if not lower_name.endswith(doc_exts):
                    # 比如 https://www.example.com/article
                    return "MinerU-HTML"
            
            # 其他情况返回用户指定的模型 (默认为 vlm)
            return user_model

        # 扫描输入
        inputs = []
        for inp in args.inputs:
            if is_url(inp):
                inputs.append(('url', inp))
            else:
                p = Path(inp)
                if p.is_dir():
                    for ext in ['*.pdf', '*.doc', '*.docx', '*.ppt', '*.pptx', '*.html']:
                        for f in p.glob(ext):
                            inputs.append(('local', f))
                elif p.exists():
                    inputs.append(('local', p))
                else:
                    print(f"⚠️ 警告: 找不到文件 {inp}")

        if not inputs:
            print("❌ 没有有效的文件或URL输入")
            return

        # 分组
        for src_type, item in inputs:
            # 决定该文件/URL应使用的模型
            # 如果用户显式为了某个特殊用途指定了 model (比如 vlm 也可以跑 html截图?), 
            # 但官方文档强烈建议 HTML 用 MinerU-HTML。这里我们做个智能修正：
            # 如果是明确的 HTML 格式，强制使用 MinerU-HTML，除非用户真的很想用 vlm (暂不复杂化，优先稳定性)
            
            target_model = get_smart_model(str(item), args.model)
            
            # 如果用户指定了 model 且不是默认 vlm，且我们的智能判断觉得是 vlm，那还是听用户的
            # 例如用户选 pipeline，我们智能判断是 vlm -> 听用户的 pipeline
            if args.model != 'vlm' and target_model == 'vlm':
                target_model = args.model
                
            key = (src_type, target_model)
            if key not in task_groups:
                task_groups[key] = []
            task_groups[key].append(item)

        # 依次执行各组任务
        total_batches = len(task_groups)
        print(f"🧩 智能规划: 将分为 {total_batches} 个批次执行 (基于文件类型和模型需求)")
        
        for idx, ((src_type, model), items) in enumerate(task_groups.items(), 1):
            print(f"\n🚀 --- 批次 {idx}/{total_batches} [{src_type.upper()} | {model}] ---")
            
            try:
                name_to_folder = {}  # 文件名→路径编码文件夹名映射
                
                if src_type == 'local':
                    print(f"📡 正在处理 {len(items)} 个本地文件...")
                    
                    # 构建文件名→路径编码文件夹名的映射
                    for fpath in items:
                        name_to_folder[fpath.name] = path_to_folder_name(fpath)
                    
                    # 缓存检查：跳过已转换的文件
                    uncached = []
                    for fpath in items:
                        cached_dir = out_dir / name_to_folder[fpath.name]
                        if cached_dir.exists() and list(cached_dir.glob("*.md")):
                            print(f"   ⏭️ 已缓存，跳过: {fpath.name}")
                        else:
                            uncached.append(fpath)
                    
                    if not uncached:
                        print("✅ 所有文件已有缓存，无需转换")
                        continue
                    
                    if len(uncached) < len(items):
                        print(f"   📋 {len(items) - len(uncached)} 个已缓存，{len(uncached)} 个需转换")
                    items = uncached
                    
                    fnames = [f.name for f in items]
                    
                    # 1. 申请上传链接（同时获得 batch_id）
                    batch_id, file_urls = client.apply_upload_urls(fnames, model_version=model)
                    
                    # 2. 上传文件（上传完成后系统自动提交解析任务）
                    for i, fpath in enumerate(items):
                        print(f"   ⬆️ 上传: {fpath.name}")
                        client.upload_file(file_urls[i], fpath)
                    
                    print(f"✨ 文件上传完成，系统自动提交解析! Batch ID: {batch_id}")
                        
                else: # url
                    print(f"🔗 正在处理 {len(items)} 个网络链接...")
                    files_info = []
                    for u in items:
                        info = {"url": u}
                        if args.pages: info["page_ranges"] = args.pages
                        files_info.append(info)
                
                    # URL 需要主动提交 extract_batch
                    print("📨 提交处理请求...")
                    batch_id = client.extract_batch(
                        files_info=files_info,
                        model_version=model,
                        enable_formula=not args.no_formula,
                        enable_table=not args.no_table,
                        language=args.language,
                        extra_formats=args.extra_formats
                    )
                    
                    print(f"✨ 批次任务已创建! Batch ID: {batch_id}")
                
                # 4. 异步或等待
                if args.no_wait:
                    print(f"🚀 已异步提交。ID: {batch_id}")
                    continue
                
                # 等待逻辑
                targets = [f.name for f in items] if src_type == 'local' else items
                result_data = client.wait_for_batch(batch_id, targets)
                
                # 5. 下载
                print(f"💾 开始下载结果 -> {out_dir}")
                for res in result_data.get("extract_result", []):
                     if res.get("state") == "done":
                        zip_url = res.get("full_zip_url")
                        fname = res.get("file_name") or "unknown_file"
                        stem = Path(fname).stem
                        
                        # 使用路径编码文件夹名（本地文件）或清洗后文件名（URL）
                        if fname in name_to_folder:
                            folder = name_to_folder[fname]
                        else:
                            folder = client._sanitize_filename(stem)
                        doc_out = out_dir / folder
                        doc_out.mkdir(parents=True, exist_ok=True)
                        
                        saved_path = client.download_result(zip_url, doc_out, stem, args.extra_formats)
                        if saved_path:
                            print(f"   ✅ 完成: {saved_path}")
                        else:
                            print(f"   ⚠️ 下载解压异常: {fname}")
                     else:
                        print(f"   ❌ 失败: {res.get('file_name')} ({res.get('err_msg')})")

            except Exception as e:
                print(f"❌ 本批次执行出错: {e}")

    # === 处理 查询 逻辑 ===
    elif args.command == "query":
        batch_id = args.batch_id
        print(f"🔍 查询任务: {batch_id}")
        
        data = client.get_batch_results(batch_id)
        results = data.get("extract_result", [])
        
        if not results:
             print("⚠️ 未查询到有效结果或任务不存在")
             return

        # 检查是否全部完成
        all_finished = True
        for res in results:
            print(f" > 文件: {res.get('file_name')} | 状态: {res.get('state')}")
            if res.get("state") not in ["done", "failed"]:
                all_finished = False
        
        if all_finished:
            print("\n💾 任务已归档，准备下载...")
            for res in results:
                if res.get("state") == "done":
                    url = res.get("full_zip_url")
                    fname = res.get("file_name")
                    stem = Path(fname).stem
                    doc_out = out_dir / stem
                    doc_out.mkdir(parents=True, exist_ok=True)
                    
                    p = client.download_result(url, doc_out, stem)
                    print(f"   ✅ 已保存至: {p}")
        else:
            print("\n⏳ 任务尚未全部完成，请稍后再试，或包含 --wait (暂未实现query wait) 逻辑")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断操作")
    except MinerUError as e:
        print(f"\n❌ MinerU 错误: {e}")
    except Exception as e:
        print(f"\n❌ 未知系统错误: {e}")
        import traceback
        traceback.print_exc()
