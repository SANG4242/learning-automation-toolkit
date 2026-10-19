"""
同济大学教务系统课表导出助手 (支持本地双重缓存)

命令行用法：
  1. 查询所有学期及其对应的 ID (优先读取本地缓存，加 --refresh 强制刷新)：
     python export_schedule.py list-semesters [--refresh]
     
  2. 导出指定学期的课表数据 (优先读取本地缓存，加 --refresh 强制刷新)：
     python export_schedule.py export [-c <学期ID>] [-f <csv|json>] [-o <输出文件路径>] [--refresh]
     
参数说明：
  list-semesters    显示所有可用的学期名称与对应的 calendarId 映射关系。
  export            执行课表导出。
  -c, --calendar    指定要导出的学期 ID（默认：122，即 2026-2027学年第1学期）。
  -f, --format      指定导出格式，可选 csv 或 json（默认：csv）。
  -o, --output      自定义输出文件的绝对路径。
  --refresh         强制绕过本地缓存，重新向一系统线上拉取最新数据。
"""

import os
import sys
import json
import sqlite3
import shutil
import tempfile
import urllib.request
import urllib.parse
import re
import csv
import time

# 统一缓存与默认输出目录
CACHE_DIR = os.environ.get("LEARNING_SCHEDULE_CACHE", os.path.join(os.path.dirname(__file__), ".cache"))
SEMESTER_CACHE_FILE = os.path.join(CACHE_DIR, "semesters_cache.json")

def get_firefox_sessionid():
    """从 Firefox LocalStorage 中解析 sessiondata 获取真正的 sessionid (X-Token)"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    firefox_profiles_dir = os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
    if not os.path.exists(firefox_profiles_dir):
        return None
    
    for d in os.listdir(firefox_profiles_dir):
        profile_path = os.path.join(firefox_profiles_dir, d)
        if os.path.isdir(profile_path):
            db_path = os.path.join(profile_path, "storage", "default", "https+++1.tongji.edu.cn", "ls", "data.sqlite")
            if os.path.exists(db_path):
                temp_db = os.path.join(tempfile.gettempdir(), "ff_ls_export_schedule_cache.sqlite")
                try:
                    shutil.copy2(db_path, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT key, value FROM data")
                    rows = cursor.fetchall()
                    conn.close()
                    os.remove(temp_db)
                    
                    for key, val in rows:
                        try:
                            k_str = key.decode('utf-16') if isinstance(key, bytes) else str(key)
                        except Exception:
                            k_str = ""
                        
                        if k_str == "sessiondata":
                            m = re.search(rb'"sessionid"\s*:\s*"([a-f0-9]{32})"', val)
                            if m:
                                return m.group(1).decode('utf-8')
                except Exception as e:
                    print(f"⚠️ 读取 Firefox LocalStorage 失败: {e}", file=sys.stderr)
    return None

def get_firefox_cookies():
    """从 Firefox cookies 数据库中提取 tongji.edu.cn 的 Cookie"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return {}
    firefox_profiles_dir = os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
    if not os.path.exists(firefox_profiles_dir):
        return {}
    
    for d in os.listdir(firefox_profiles_dir):
        profile_path = os.path.join(firefox_profiles_dir, d)
        if os.path.isdir(profile_path):
            cookies_db = os.path.join(profile_path, "cookies.sqlite")
            if os.path.exists(cookies_db):
                temp_db = os.path.join(tempfile.gettempdir(), "temp_cookies_export_sch_cache.sqlite")
                try:
                    shutil.copy2(cookies_db, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT name, value FROM moz_cookies WHERE host LIKE '%tongji.edu.cn%'"
                    )
                    rows = cursor.fetchall()
                    conn.close()
                    os.remove(temp_db)
                    if rows:
                        return {name: value for name, value in rows}
                except Exception as e:
                    print(f"⚠️ 提取 Firefox Cookie 失败: {e}", file=sys.stderr)
    return {}

def print_semesters_table(items):
    """规整打印学期对照表"""
    print("\n" + "="*70)
    print(f"{'学期 ID':<10} | {'学期名称':<30} | {'年度':<10} | {'学期'}")
    print("-"*70)
    for item in items:
        print(f"{str(item.get('id')):<10} | {str(item.get('fullName')):<30} | {str(item.get('year')):<10} | {str(item.get('term'))}")
    print("="*70 + "\n")

def list_semesters(cookies, sessionid, force_refresh=False):
    """获取并显示学期列表 (支持本地缓存)"""
    # 优先读取本地缓存
    if not force_refresh and os.path.exists(SEMESTER_CACHE_FILE):
        print(f"📖 优先读取本地学期映射缓存: {SEMESTER_CACHE_FILE}")
        try:
            with open(SEMESTER_CACHE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
            print_semesters_table(items)
            return
        except Exception as e:
            print(f"⚠️ 加载学期缓存失败: {e}，将重新联网拉取。")
            
    # 线上拉取
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "X-Token": sessionid,
        "Accept": "application/json, text/plain, */*"
    }
    
    url = "https://1.tongji.edu.cn/api/baseresservice/schoolCalendar/list"
    req = urllib.request.Request(url, headers=headers, method="GET")
    
    print("📡 正在从教务系统线上拉取最新学期列表...")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            if res_json.get("code") == 200:
                items = res_json.get("data", [])
                print_semesters_table(items)
                # 写入缓存
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(SEMESTER_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=4)
                print(f"💾 学期映射数据已缓存至: {SEMESTER_CACHE_FILE}")
            else:
                print(f"❌ 获取学期列表失败: {res_json.get('msg')}", file=sys.stderr)
    except Exception as e:
        print(f"❌ 网络请求异常: {e}", file=sys.stderr)

def fetch_schedule_from_onesystem(cookies, sessionid, calendar_id):
    """采用分页并发安全模式拉取一系统全校排课列表"""
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    if "sessionid" not in cookies and sessionid:
        cookie_str += f"; sessionid={sessionid}"
        
    url = "https://1.tongji.edu.cn/api/arrangementservice/manualArrange/page?profile"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Referer": "https://1.tongji.edu.cn/taskResultQuery",
        "Origin": "https://1.tongji.edu.cn",
        "Cookie": cookie_str,
        "Accept": "application/json, text/plain, */*",
        "X-Token": sessionid
    }
    
    page_size = 500
    page_num = 1
    all_records = []
    
    print(f"📡 正在从教务系统线上拉取学期 {calendar_id} 的全量排课数据...")
    
    while True:
        payload = {
            "pageNum_": page_num,
            "pageSize_": page_size,
            "condition": {
                "trainingLevel": "",
                "campus": "",
                "calendar": int(calendar_id),
                "college": "",
                "isChineseTeaching": None,
                "ids": [],
                "course": ""
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                if res_json.get("code") != 200:
                    print(f"❌ 分页抓取失败，页码: {page_num}，原因: {res_json.get('msg')}", file=sys.stderr)
                    break
                
                total = res_json.get("data", {}).get("total_", 0)
                records = res_json.get("data", {}).get("list", [])
                
                if not records:
                    break
                    
                all_records.extend(records)
                print(f"  - 进度: 已拉取 {len(all_records)} / {total} 条记录 (第 {page_num} 页)")
                
                if len(all_records) >= total:
                    break
                    
                page_num += 1
                time.sleep(0.4)
        except Exception as e:
            print(f"❌ 分页网络请求异常，页码: {page_num}，原因: {e}", file=sys.stderr)
            break
            
    print(f"✅ 线上数据抓取完成，共拉取到 {len(all_records)} 条记录。")
    return all_records

def sanitize_csv_fields(record):
    """解析嵌套的班级和老师数据为扁平 CSV 字段"""
    teachers = []
    t_list = record.get("teacherList")
    if t_list:
        for t in t_list:
            t_name = t.get("teacherName")
            t_code = t.get("teacherCode")
            if t_name:
                teachers.append(f"{t_name}({t_code})" if t_code else t_name)
    teachers_str = ",".join(teachers) if teachers else record.get("teacherName") or ""
    
    def sanitize(val):
        return "" if val is None else str(val)

    return {
        "课程序号": sanitize(record.get("code")),
        "课程代码": sanitize(record.get("courseCode")),
        "课程名称": sanitize(record.get("courseName")),
        "开课学院": sanitize(record.get("facultyI18n")),
        "学分": sanitize(record.get("credits")),
        "学时": sanitize(record.get("period")),
        "任课教师": sanitize(teachers_str),
        "排课信息": sanitize(record.get("arrangeInfo")),
        "额定人数": sanitize(record.get("number")),
        "选课人数": sanitize(record.get("elcNumber")),
        "考核方式": sanitize(record.get("assessmentModeI18n")),
        "课程性质": sanitize(record.get("courseLabelName"))
    }

def export_data(records, fmt, out_path):
    """根据指定格式导出数据到文件"""
    if not records:
        print("⚠️ 导出的课表记录为空，取消导出。")
        return
        
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    
    try:
        if fmt == "json":
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=4)
        else:
            fieldnames = ["课程序号", "课程代码", "课程名称", "开课学院", "学分", "学时", "任课教师", "排课信息", "额定人数", "选课人数", "考核方式", "课程性质"]
            with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for rec in records:
                    writer.writerow(sanitize_csv_fields(rec))
        print(f"\n🎉 成功将数据转换并导出为 {fmt.upper()} 文件！")
        print(f"📂 导出路径: {out_path}")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}", file=sys.stderr)

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit(0)
        
    cmd = sys.argv[1]
    force_refresh = "--refresh" in sys.argv
    
    # 优先获取本地缓存路径
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if cmd == "list-semesters":
        # 只有在强制刷新或者缓存不存在时才需要提取凭证
        if force_refresh or not os.path.exists(SEMESTER_CACHE_FILE):
            sessionid = get_firefox_sessionid()
            cookies = get_firefox_cookies()
            if not sessionid:
                print("❌ 提取 Firefox 鉴权凭证失败。请确保您已在 Firefox 中成功登录同济教务系统。", file=sys.stderr)
                sys.exit(1)
            list_semesters(cookies, sessionid, force_refresh=True)
        else:
            list_semesters(None, None, force_refresh=False)
        
    elif cmd == "export":
        # 解析参数
        calendar_id = "122"
        fmt = "csv"
        out_path = None
        
        if "-c" in sys.argv:
            idx = sys.argv.index("-c")
            calendar_id = sys.argv[idx + 1]
        elif "--calendar" in sys.argv:
            idx = sys.argv.index("--calendar")
            calendar_id = sys.argv[idx + 1]
            
        if "-f" in sys.argv:
            idx = sys.argv.index("-f")
            fmt = sys.argv[idx + 1].lower()
        elif "--format" in sys.argv:
            idx = sys.argv.index("--format")
            fmt = sys.argv[idx + 1].lower()
            
        if fmt not in ("csv", "json"):
            print("❌ 不支持的导出格式，仅支持 csv 或 json。", file=sys.stderr)
            sys.exit(1)
            
        if "-o" in sys.argv:
            idx = sys.argv.index("-o")
            out_path = sys.argv[idx + 1]
        elif "--output" in sys.argv:
            idx = sys.argv.index("--output")
            out_path = sys.argv[idx + 1]
            
        if not out_path:
            out_path = os.path.join(CACHE_DIR, f"tongji_{calendar_id}_schedule.{fmt}")
            
        raw_cache_path = os.path.join(CACHE_DIR, f"tongji_{calendar_id}_raw.json")
        records = None
        
        # 优先从本地缓存加载原始排课列表
        if not force_refresh and os.path.exists(raw_cache_path):
            print(f"📖 发现本地原始课表数据缓存: {raw_cache_path}")
            try:
                with open(raw_cache_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                print(f"✅ 成功从本地原始数据缓存加载了 {len(records)} 条记录，避免了线上拉取。")
            except Exception as e:
                print(f"⚠️ 读取本地课表缓存失败: {e}，将重新联网拉取。")
                
        # 若无缓存或强制刷新，则向一系统联网抓取
        if not records:
            sessionid = get_firefox_sessionid()
            cookies = get_firefox_cookies()
            if not sessionid:
                print("❌ 提取 Firefox 鉴权凭证失败。请确保您已在 Firefox 中成功登录同济教务系统。", file=sys.stderr)
                sys.exit(1)
                
            records = fetch_schedule_from_onesystem(cookies, sessionid, calendar_id)
            if records:
                try:
                    with open(raw_cache_path, "w", encoding="utf-8") as f:
                        json.dump(records, f, ensure_ascii=False, indent=4)
                    print(f"💾 原始课表数据已成功缓存至: {raw_cache_path}")
                except Exception as e:
                    print(f"⚠️ 保存原始数据缓存失败: {e}")
                    
        # 执行格式导出
        export_data(records, fmt, out_path)
    else:
        print(f"❌ 未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
