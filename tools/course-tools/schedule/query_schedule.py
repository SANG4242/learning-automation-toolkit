import os
import sys
import csv
import subprocess

# 2024级相对学期与一系统 calendarId 映射表
SEMESTER_MAP = {
    "大一上": 118,
    "大一下": 119,
    "大二上": 120,
    "大二下": 121,
    "大三上": 122,
    "大三下": 123,
    "大四上": 124,
    "大四下": 125,
}

# 别名映射
ALIAS_MAP = {
    "大一第一学期": "大一上", "大一1": "大一上",
    "大一第二学期": "大一下", "大一2": "大一下",
    "大二第一学期": "大二上", "大二1": "大二上",
    "大二第二学期": "大二下", "大二2": "大二下",
    "大三第一学期": "大三上", "大三1": "大三上",
    "大三第二学期": "大三下", "大三2": "大三下",
    "大四第一学期": "大四上", "大四1": "大四上",
    "大四第二学期": "大四下", "大四2": "大四下",
}

CACHE_DIR = os.environ.get("LEARNING_SCHEDULE_CACHE", os.path.join(os.path.dirname(__file__), ".cache"))

def print_mapping():
    """打印相对学期与一系统 ID 对照表"""
    print("\n" + "="*50)
    print(f"{'相对学期':<10} | {'学年学期':<25} | {'一系统 ID (calendarId)'}")
    print("-"*50)
    sem_names = {
        118: "2024-2025学年第1学期",
        119: "2024-2025学年第2学期",
        120: "2025-2026学年第1学期",
        121: "2025-2026学年第2学期",
        122: "2026-2027学年第1学期",
        123: "2026-2027学年第2学期",
        124: "2027-2028学年第1学期",
        125: "2027-2028学年第2学期",
    }
    for term, cid in SEMESTER_MAP.items():
        name = sem_names.get(cid, "未知学年学期")
        print(f"{term:<10} | {name:<25} | {cid}")
    print("="*50 + "\n")

def parse_semester(term_str):
    """解析输入的学期字符串为 calendarId"""
    term_str = term_str.strip()
    if term_str in SEMESTER_MAP:
        return SEMESTER_MAP[term_str]
    if term_str in ALIAS_MAP:
        return SEMESTER_MAP[ALIAS_MAP[term_str]]
    
    # 尝试直接解析数字
    try:
        cid = int(term_str)
        return cid
    except ValueError:
        return None

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("同济全校排课本地检索助手")
        print("用法:")
        print("  python query_schedule.py --show-semesters                  # 显示学期与 ID 的对照表")
        print("  python query_schedule.py <相对学期|学期ID> <查询关键词>    # 查询某学期的课表")
        print("\n示例:")
        print("  python query_schedule.py 大二下 计算机网络实验")
        print("  python query_schedule.py 121 冯巾松")
        sys.exit(0)

    if sys.argv[1] in ("--show-semesters", "-s"):
        print_mapping()
        sys.exit(0)

    if len(sys.argv) < 3:
        print("❌ 错误: 请指定查询关键词。用法: python query_schedule.py <学期> <关键词>")
        sys.exit(1)

    term_input = sys.argv[1]
    keyword = sys.argv[2]

    calendar_id = parse_semester(term_input)
    if not calendar_id:
        print(f"❌ 无法识别的学期输入: '{term_input}'")
        print("提示: 可输入 '大二下' 等相对学期，或直接输入教务系统的学期 ID（如 121）。")
        sys.exit(1)

    csv_name = f"tongji_{calendar_id}_schedule.csv"
    csv_path = os.path.join(CACHE_DIR, csv_name)

    # 如果本地缓存文件不存在，则自动尝试调用 export_schedule.py 进行拉取和导出
    if not os.path.exists(csv_path):
        print(f"⚠️ 未发现本地 CSV 课表缓存 (ID: {calendar_id})，将自动运行导出脚本...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        export_script = os.path.join(script_dir, "export_schedule.py")
        
        if not os.path.exists(export_script):
            print(f"❌ 未找到底层导出脚本: {export_script}")
            sys.exit(1)

        try:
            # 运行导出命令
            cmd = ["python", export_script, "export", "-c", str(calendar_id), "-f", "csv"]
            print(f"执行命令: {' '.join(cmd)}")
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            print(res.stdout)
            if res.stderr:
                print(res.stderr, file=sys.stderr)
        except Exception as e:
            print(f"❌ 调用导出脚本失败: {e}", file=sys.stderr)
            sys.exit(1)

        if not os.path.exists(csv_path):
            print("❌ 自动导出课表失败。请确保您已在 Firefox 中登录同济教务系统，然后手动尝试运行 export_schedule.py。")
            sys.exit(1)

    # 开始检索本地 CSV
    print(f"🔎 正在本地检索 {term_input} (ID: {calendar_id}) 的课表，关键词: '{keyword}'...")
    
    results = []
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 在课程名称、任课教师、排课信息中进行检索
                cname = row.get("课程名称", "")
                teacher = row.get("任课教师", "")
                arrange = row.get("排课信息", "")
                ccode = row.get("课程代码", "")
                
                if keyword in cname or keyword in teacher or keyword in arrange or keyword in ccode:
                    results.append(row)
    except Exception as e:
        print(f"❌ 读取 CSV 文件出错: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✨ 检索完成，共找到 {len(results)} 条匹配记录:\n")
    if not results:
        print("（无匹配记录）")
        return

    for idx, row in enumerate(results, 1):
        print(f"[{idx}] 课程代码: {row.get('课程代码')} | 课程序号: {row.get('课程序号')}")
        print(f"    课程名称: {row.get('课程名称')} ({row.get('课程性质')})")
        print(f"    学分/学时: {row.get('学分')} / {row.get('学时')}")
        print(f"    任课教师: {row.get('任课教师')}")
        print(f"    排课信息: {row.get('排课信息')}")
        print(f"    人数限额: 选课人数 {row.get('选课人数')} / 额定人数 {row.get('额定人数')}")
        print("-" * 60)

if __name__ == "__main__":
    main()
