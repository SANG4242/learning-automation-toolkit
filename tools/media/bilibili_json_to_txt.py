import os
import json
import argparse

def format_time(seconds):
    """将秒数转换为 [HH:MM:SS] 或 [MM:SS] 格式"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"

def convert_file(input_path, output_path=None, use_txt=False):
    """转换单个 JSON 字幕文件"""
    if not os.path.exists(input_path):
        print(f"错误: 输入文件 {input_path} 不存在")
        return False
        
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"解析 JSON 失败: {e}")
        return False
        
    if not isinstance(data, list):
        # 兼容其他可能的B站JSON格式，例如包含 'body' -> 'subtitles' 的结构
        if isinstance(data, dict) and "body" in data:
            data = data["body"]
        if isinstance(data, dict) and "subtitles" in data:
            data = data["subtitles"]
            
    if not isinstance(data, list):
        print("错误: JSON 格式不符合预期 (应为包含字幕条目的列表)")
        return False

    lines = []
    for item in data:
        start_sec = item.get("from") if item.get("from") is not None else item.get("start")
        content = item.get("content") or item.get("text") or ""
        
        if start_sec is not None:
            time_str = format_time(float(start_sec))
            lines.append(f"[{time_str}] {content.strip()}")
        else:
            if content.strip():
                lines.append(content.strip())
                
    # 确定目标扩展名
    target_ext = ".txt" if use_txt else ".md"
    
    if not output_path:
        output_path = os.path.splitext(input_path)[0] + target_ext
    elif os.path.isdir(output_path) or not output_path.lower().endswith((".txt", ".md")):
        filename = os.path.splitext(os.path.basename(input_path))[0] + target_ext
        output_path = os.path.join(output_path, filename)
        
    try:
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"成功转换: {input_path} -> {output_path}")
        return True
    except Exception as e:
        print(f"写入文件失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="B站/Bilibili JSON 字幕转换工具")
    parser.add_argument("inputs", nargs="+", help="输入文件路径、目录路径，支持传入多个文件或文件夹")
    parser.add_argument("-o", "--output", help="输出路径 (可以是具体的 .md/.txt 文件路径，也可以是输出目录)")
    parser.add_argument("--txt", action="store_true", help="强制输出为 .txt 格式 (默认输出为 .md 格式)")
    args = parser.parse_args()
    
    files_to_convert = []
    for path in args.inputs:
        if os.path.isdir(path):
            dir_files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".json")]
            files_to_convert.extend(dir_files)
        elif os.path.isfile(path):
            files_to_convert.append(path)
        else:
            print(f"警告: 路径 {path} 既不是文件也不是目录，已跳过")
            
    if not files_to_convert:
        print("没有找到有效的 JSON 文件以供转换")
        return
        
    print(f"待转换的 JSON 文件总数: {len(files_to_convert)}")
    
    output = args.output
    if output and len(files_to_convert) > 1:
        _, ext = os.path.splitext(output)
        if ext.lower() in [".txt", ".md"]:
            print(f"警告: 多个输入文件无法合并输出到单个文件 {output}。输出路径将被视为目录 {os.path.dirname(output)}")
            output = os.path.dirname(output)

    success_count = 0
    for f in files_to_convert:
        if convert_file(f, output, use_txt=args.txt):
            success_count += 1
            
    print(f"批量转换完成: 成功 {success_count}/{len(files_to_convert)}")

if __name__ == "__main__":
    main()
