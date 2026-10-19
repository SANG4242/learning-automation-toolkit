r"""
YourTJ Hub 课程、评价与排课查询工具。

运行 `python query_yourtj.py --help` 查看完整命令，运行
`python query_yourtj.py <命令> --help` 查看对应参数。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

API_BASE = "https://f.yourtj.de"
DEFAULT_OUTPUT = os.environ.get("LEARNING_COURSE_REVIEWS_DIR", os.path.join(os.path.dirname(__file__), ".cache", "reviews"))
PAGE_SIZE = 50


def api_request(path, query_params=None, body=None, timeout=30):
    url = f"{API_BASE}{path}"
    if query_params:
        url += "?" + urllib.parse.urlencode(query_params, doseq=True)
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "YourTJ-Course-CLI/3.0",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.headers.get_content_type() != "application/json":
                raise RuntimeError(f"接口返回了非 JSON 内容：{response.headers.get_content_type()}")
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            message = parsed.get("messageCode") or parsed.get("msg") or raw[:200]
        except json.JSONDecodeError:
            message = raw[:200]
        raise RuntimeError(f"HTTP {error.code}: {message or error.reason}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"请求失败：{error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError("接口响应格式异常")
    if payload.get("code") != 0:
        message = payload.get("messageCode") or payload.get("msg") or "未知业务错误"
        raise RuntimeError(f"接口返回错误：{message}")
    return payload


def forum_get(path, query_params=None):
    return api_request(path, query_params).get("result")


def pk_get(path, query_params=None):
    return api_request(path, query_params).get("data")


def pk_post(path, body):
    return api_request(path, body=body).get("data")


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def truncate(value, length):
    text = str(value or "")
    return text if len(text) <= length else text[: length - 2] + ".."


def course_credit(course):
    credit_x10 = course.get("creditX10")
    if not isinstance(credit_x10, (int, float)):
        return "未知"
    return f"{credit_x10 / 10:g}"


def course_teacher(course):
    return course.get("teacherName") or "无教师"


def rating_text(value):
    return "无" if value is None else f"{value:.2f}"


def search_courses(keyword="", only_with_reviews=True, departments=None, terms=None, campuses=None, instructors=None, sort_by=None):
    courses = []
    page = 1
    while True:
        params = {
            "keyword": keyword,
            "onlyWithReviews": "true" if only_with_reviews else "false",
            "page": page,
            "size": PAGE_SIZE,
        }
        if departments:
            params["department"] = departments
        if terms:
            params["term"] = terms
        if campuses:
            params["campus"] = campuses
        if instructors:
            params["instructor"] = instructors
        if sort_by:
            params["sortBy"] = sort_by
        result = forum_get("/api/forum/courses", params)
        if not isinstance(result, dict):
            raise RuntimeError("课程列表响应缺少 result")
        courses.extend(result.get("list") or [])
        if not result.get("hasNext"):
            return courses
        page += 1


def get_course_detail(course_id):
    result = forum_get(f"/api/forum/courses/{course_id}")
    if not isinstance(result, dict):
        raise RuntimeError("课程详情响应格式异常")
    return result


def get_course_reviews(course_id, offering_id=None):
    reviews = []
    cursor = None
    while True:
        params = {"pageSize": PAGE_SIZE}
        if offering_id:
            params["offeringId"] = offering_id
        if cursor:
            params["cursor"] = cursor
        result = forum_get(f"/api/forum/courses/{course_id}/reviews", params)
        if not isinstance(result, dict):
            raise RuntimeError("评价列表响应格式异常")
        reviews.extend(result.get("list") or [])
        cursor = result.get("nextCursor")
        if not cursor:
            return reviews


def print_courses_table(courses):
    if not courses:
        print("未找到匹配课程。")
        return
    print(f"{'ID':<7} | {'课程代码':<14} | {'课程名称':<24} | {'学分':<4} | {'教师':<10} | {'开课单位':<20} | {'评分':<5} | 评价数")
    print("-" * 115)
    for course in courses:
        print(
            f"{str(course.get('id', '')):<7} | "
            f"{truncate(course.get('primaryCode'), 14):<14} | "
            f"{truncate(course.get('name'), 24):<24} | "
            f"{course_credit(course):<4} | "
            f"{truncate(course_teacher(course), 10):<10} | "
            f"{truncate(course.get('department'), 20):<20} | "
            f"{rating_text(course.get('ratingAvg')):<5} | "
            f"{course.get('reviewCount', 0)}"
        )


def offering_terms(course):
    return {
        offering.get("id"): offering.get("termName") or offering.get("termCode") or "未知学期"
        for offering in course.get("offerings") or []
    }


def review_date(value):
    if not value:
        return "未知"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(value)


def review_author(review):
    return (review.get("author") or {}).get("label") or "匿名同学"


def print_offerings(course):
    offerings = course.get("offerings") or []
    if not offerings:
        print("\n无公开教学班信息。")
        return
    print("\n===== 教学班 =====")
    for offering in offerings:
        teachers = "、".join(offering.get("instructors") or []) or "未知"
        term = offering.get("termName") or offering.get("termCode") or "未知学期"
        stats = f"评分 {rating_text(offering.get('ratingAvg'))}，{offering.get('reviewCount', 0)} 条评价"
        print(
            f"offeringId={offering.get('id')} | {term} | {offering.get('classCode') or '无班号'} "
            f"{offering.get('className') or ''} | {teachers} | {offering.get('campus') or '未知校区'} | {stats}"
        )


def print_reviews(course, reviews):
    terms = offering_terms(course)
    print(f"\n===== 公开评价（{len(reviews)} 条） =====")
    for index, review in enumerate(reviews, start=1):
        term = terms.get(review.get("offeringId"), "未知学期")
        rating = review.get("rating")
        rating_display = "无评分" if rating is None else f"{rating} 分"
        print(
            f"[{index}] {review_author(review)} | {term} | offeringId={review.get('offeringId')} | "
            f"{rating_display} | 有用 {review.get('helpfulCount', 0)} | 不喜欢 {review.get('dislikeCount', 0)}"
        )
        print((review.get("content") or "").strip())
        print("-" * 50)


def print_course_info(course, reviews=None):
    print("\n===== 课程信息 =====")
    print(f"ID: {course.get('id')}  代码: {course.get('primaryCode')}")
    print(f"名称: {course.get('name')}  学分: {course_credit(course)}")
    print(f"教师: {course_teacher(course)}  开课单位: {course.get('department')}")
    print(f"评分: {rating_text(course.get('ratingAvg'))} / 5（{course.get('reviewCount', 0)} 条评价）")
    print(f"评价范围: {course.get('reviewScope') or '未知'}")
    print(f"链接: https://f.yourtj.de/courses/{course.get('id')}")
    print_offerings(course)
    if reviews is not None:
        print_reviews(course, reviews)


def format_review_markdown(course, reviews):
    terms = offering_terms(course)
    lines = [
        f"# 课程评价：{course.get('name', '未知课程')} - {course_teacher(course)}",
        "",
        f"> 开课单位：{course.get('department') or '未知'}",
        f"> 课程代码：`{course.get('primaryCode') or '未知'}` | 学分：{course_credit(course)}",
        f"> 平均评分：{rating_text(course.get('ratingAvg'))} / 5（{course.get('reviewCount', 0)} 条评价）",
        f"> YourTJ 链接：<https://f.yourtj.de/courses/{course.get('id', '')}>",
        "",
        "---",
        "",
        f"## 评价列表（{len(reviews)} 条）",
        "",
    ]
    for review in reviews:
        term = terms.get(review.get("offeringId"), "未知学期")
        rating = review.get("rating")
        rating_display = "无评分" if rating is None else f"{rating} 分"
        lines.extend(
            [
                f"### {review_author(review)} | {term} | {rating_display} | 有用 {review.get('helpfulCount', 0)}",
                f"> 发布时间：{review_date(review.get('createdAt'))}",
                "",
                (review.get("content") or "").strip(),
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def safe_filename(text):
    value = "".join(char for char in text if char.isalnum() or char in ("-", "_", " ")).strip()
    return value or "未知课程"


def dump_course(course_id, output_dir):
    course = get_course_detail(course_id)
    reviews = get_course_reviews(course_id)
    filename = safe_filename(f"{course_teacher(course)}_{course.get('name', '未知课程')}") + ".md"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as output:
        output.write(format_review_markdown(course, reviews))
    print(f"已导出 {len(reviews)} 条评价：{filepath}")


def refresh_directory(source_dir, output_dir):
    if not os.path.isdir(source_dir):
        raise RuntimeError(f"旧点评目录不存在：{source_dir}")
    if os.path.abspath(source_dir) == os.path.abspath(output_dir):
        raise RuntimeError("新旧目录不能相同")
    source_files = sorted(name for name in os.listdir(source_dir) if name.lower().endswith(".md"))
    if not source_files:
        raise RuntimeError("旧点评目录中没有 Markdown 文件")
    os.makedirs(output_dir, exist_ok=True)
    failures = []
    succeeded = 0
    for filename in source_files:
        stem = os.path.splitext(filename)[0]
        if "_" not in stem:
            failures.append(f"{filename}：文件名不符合 教师_课程.md")
            continue
        teacher, course_name = stem.split("_", 1)
        candidates = search_courses(course_name, only_with_reviews=True)
        exact = [course for course in candidates if course.get("name") == course_name and course_teacher(course) == teacher]
        if len(exact) != 1:
            failures.append(f"{filename}：精确匹配 {len(exact)} 项")
            continue
        dump_course(exact[0]["id"], output_dir)
        succeeded += 1
    if failures:
        raise RuntimeError(f"重建未完成：成功 {succeeded}/{len(source_files)}。\n" + "\n".join(failures))
    print(f"点评目录重建完成：{succeeded}/{len(source_files)}，输出到 {output_dir}")


def add_raw_option(parser):
    parser.add_argument("--json", action="store_true", help="输出完整原始 JSON")


def build_parser():
    parser = argparse.ArgumentParser(description="YourTJ Hub 课程、评价与排课公开数据查询工具")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="搜索课程目录")
    search.add_argument("keyword", nargs="?", default="", help="课程名、课程号或教师关键词")
    search.add_argument("--all", action="store_true", help="包含没有评价的课程；默认只显示有评价课程")
    search.add_argument("--teacher", action="append", help="教师姓名，可重复")
    search.add_argument("--department", action="append", help="开课单位，可重复")
    search.add_argument("--term", action="append", help="学期代码，如 2026-2027-1，可重复")
    search.add_argument("--campus", action="append", help="校区，可重复")
    search.add_argument("--sort", choices=["rating"], help="按评分降序")
    add_raw_option(search)

    info = sub.add_parser("info", help="查看课程详情、教学班和评价")
    info.add_argument("course_id", type=int, help="新版 YourTJ courseId")
    info.add_argument("--offering", type=int, help="只读取指定 offeringId 的评价")
    info.add_argument("--no-reviews", action="store_true", help="只显示详情和教学班")
    add_raw_option(info)

    reviews = sub.add_parser("reviews", help="读取课程评价")
    reviews.add_argument("course_id", type=int)
    reviews.add_argument("--offering", type=int, help="只读取指定教学班评价")
    add_raw_option(reviews)

    related = sub.add_parser("related", help="查看同教师其他课程、同课程其他教师及沿革")
    related.add_argument("course_id", type=int)
    add_raw_option(related)

    summary = sub.add_parser("summary", help="读取课程 AI 评价总结")
    summary.add_argument("course_id", type=int)
    summary.add_argument("--generate", action="store_true", help="没有缓存时允许生成总结")
    summary.add_argument("--refresh", action="store_true", help="强制重新生成，可能触发限流")
    add_raw_option(summary)

    dump = sub.add_parser("dump", help="导出一门课程的全部评价")
    dump.add_argument("course_id", type=int)
    dump.add_argument("-o", "--output", default=DEFAULT_OUTPUT)

    dump_search = sub.add_parser("dump-search", help="搜索并批量导出有评价课程")
    dump_search.add_argument("keyword")
    dump_search.add_argument("-o", "--output", default=DEFAULT_OUTPUT)

    refresh = sub.add_parser("refresh-dir", help="按 教师_课程.md 重建点评目录")
    refresh.add_argument("source_dir")
    refresh.add_argument("-o", "--output", required=True)

    calendars = sub.add_parser("schedule-calendars", help="列出 YourTJ 排课器学期")
    add_raw_option(calendars)
    dictionaries = sub.add_parser("schedule-dictionaries", help="列出校区和开课学院字典")
    add_raw_option(dictionaries)

    grades = sub.add_parser("schedule-grades", help="查询某学期可选年级")
    grades.add_argument("calendar_id", type=int)
    add_raw_option(grades)

    majors = sub.add_parser("schedule-majors", help="查询年级对应专业")
    majors.add_argument("grade", type=int)
    majors.add_argument("--calendar", type=int)
    add_raw_option(majors)

    major_courses = sub.add_parser("schedule-major-courses", help="查询专业培养计划课程及教学班")
    major_courses.add_argument("calendar_id", type=int)
    major_courses.add_argument("grade", type=int)
    major_courses.add_argument("major_code")
    add_raw_option(major_courses)

    optional = sub.add_parser("schedule-optional-types", help="查询某学期选修课程类型")
    optional.add_argument("calendar_id", type=int)
    add_raw_option(optional)

    nature = sub.add_parser("schedule-nature-courses", help="按课程性质 ID 查询课程")
    nature.add_argument("calendar_id", type=int)
    nature.add_argument("nature_ids", type=int, nargs="+")
    add_raw_option(nature)

    schedule_search = sub.add_parser("schedule-search", help="高级搜索排课课程，最多返回 100 门")
    schedule_search.add_argument("calendar_id", type=int)
    schedule_search.add_argument("--name", help="课程名")
    schedule_search.add_argument("--code", help="课程代码")
    schedule_search.add_argument("--teacher", help="教师姓名")
    schedule_search.add_argument("--teacher-code", help="教师工号")
    schedule_search.add_argument("--campus", help="校区")
    schedule_search.add_argument("--faculty", help="开课学院")
    add_raw_option(schedule_search)

    detail = sub.add_parser("schedule-detail", help="查询课程的教学班、时间、地点和教师")
    detail.add_argument("calendar_id", type=int)
    detail.add_argument("course_codes", nargs="+")
    add_raw_option(detail)

    by_time = sub.add_parser("schedule-time", help="按星期和排课器节次组查询课程")
    by_time.add_argument("calendar_id", type=int)
    by_time.add_argument("day", type=int, choices=range(1, 8), help="1=周一，7=周日")
    by_time.add_argument("section", type=int, choices=range(1, 7), help="1..6 对应 1-2/3-4/5-6/7-8/9/10")
    add_raw_option(by_time)

    review = sub.add_parser("schedule-review", help="按排课课程或教学班查询课评摘要")
    review.add_argument("course_code")
    review.add_argument("--teacher")
    review.add_argument("--calendar", type=int)
    review.add_argument("--class-id", type=int, help="一系统教学班 ID，可精准匹配")
    add_raw_option(review)

    latest = sub.add_parser("schedule-latest", help="查看排课数据最近同步时间")
    add_raw_option(latest)
    sections = sub.add_parser("schedule-section-times", help="查看排课器节次作息表")
    add_raw_option(sections)
    return parser


def print_pk_courses(courses):
    if not courses:
        print("未找到匹配排课课程。")
        return
    print(f"{'课程代码':<16} | {'课程名称':<26} | {'学分':<4} | {'学院':<24} | 校区")
    print("-" * 105)
    for course in courses:
        campuses = course.get("campus") or course.get("campus_list") or []
        if isinstance(campuses, str):
            campuses = [campuses]
        print(
            f"{truncate(course.get('courseCode'), 16):<16} | {truncate(course.get('courseName'), 26):<26} | "
            f"{str(course.get('credit', '')):<4} | {truncate(course.get('facultyI18n') or course.get('faculty'), 24):<24} | "
            f"{'、'.join(campuses)}"
        )


def print_pk_details(details):
    if isinstance(details, dict):
        items = [(code, rows) for code, rows in details.items()]
    else:
        items = [("", details or [])]
    for course_code, rows in items:
        if course_code:
            print(f"\n## {course_code}")
        for row in rows:
            teachers = "、".join(item.get("teacherName", "") for item in row.get("teachers") or []) or "未知"
            print(
                f"教学班 {row.get('code')} | teachingClassId={row.get('teachingClassId', '未知')} | "
                f"{teachers} | {row.get('campus') or '未知校区'} | {row.get('teachingLanguage') or '未知语言'}"
            )
            for arrangement in row.get("arrangementInfo") or []:
                print(f"  - {arrangement.get('arrangementText') or arrangement.get('occupyRoom') or '无排课文字'}")


def print_pk_grouped_courses(groups):
    if not groups:
        print("未找到匹配排课课程。")
        return
    for group in groups:
        label = group.get("courseLabelName") or "未分类"
        print(f"\n## {label}（性质 ID：{group.get('courseLabelId')}）")
        print_pk_courses(group.get("courses") or [])


def print_pk_major_courses(courses):
    if not courses:
        print("未找到该专业的培养计划课程。")
        return
    for course in courses:
        print(
            f"\n## {course.get('courseName')}（{course.get('courseCode')}） | "
            f"{course.get('credit', '')} 学分 | 年级 {course.get('grade', '')} | "
            f"{'、'.join(course.get('courseNature') or [])}"
        )
        print_pk_details(course.get("courses") or [])


def handle_command(args):
    if args.command == "search":
        courses = search_courses(args.keyword, not args.all, args.department, args.term, args.campus, args.teacher, args.sort)
        print_json(courses) if args.json else print_courses_table(courses)
    elif args.command == "info":
        course = get_course_detail(args.course_id)
        reviews = None if args.no_reviews else get_course_reviews(args.course_id, args.offering)
        print_json({"course": course, "reviews": reviews}) if args.json else print_course_info(course, reviews)
    elif args.command == "reviews":
        course = get_course_detail(args.course_id)
        reviews = get_course_reviews(args.course_id, args.offering)
        print_json(reviews) if args.json else print_reviews(course, reviews)
    elif args.command == "related":
        result = forum_get(f"/api/forum/courses/{args.course_id}/related") or {}
        if args.json:
            print_json(result)
        else:
            print("同教师其他课程：")
            print_courses_table(result.get("teacherOtherCourses") or [])
            print("\n同课程其他教师：")
            print_courses_table(result.get("sameCourseOtherTeachers") or [])
            if result.get("lineage"):
                print("\n课程沿革：")
                print_json(result["lineage"])
    elif args.command == "summary":
        params = {"refresh": "true"} if args.refresh else None
        if not args.generate and not args.refresh:
            check = forum_get(f"/api/forum/courses/{args.course_id}/summary", {"check": "true"}) or {}
            if check.get("status") != "cached":
                result = check
            else:
                result = forum_get(f"/api/forum/courses/{args.course_id}/summary") or {}
        else:
            result = forum_get(f"/api/forum/courses/{args.course_id}/summary", params) or {}
        if args.json:
            print_json(result)
        else:
            print(f"状态：{result.get('status')}")
            summary = result.get("summary") or {}
            if summary:
                print(f"共识：{summary.get('consensus')}")
                print(f"关键词：{'、'.join(summary.get('keywords') or [])}")
                print("优点：" + "；".join(summary.get("pros") or []))
                print("不足：" + "；".join(summary.get("cons") or []))
    elif args.command == "dump":
        dump_course(args.course_id, args.output)
    elif args.command == "dump-search":
        courses = search_courses(args.keyword, only_with_reviews=True)
        for course in courses:
            dump_course(course["id"], args.output)
        print(f"批量导出完成：{len(courses)} 门课程")
    elif args.command == "refresh-dir":
        refresh_directory(args.source_dir, args.output)
    elif args.command == "schedule-calendars":
        result = pk_get("/api/pk/calendars") or []
        if args.json:
            print_json(result)
        else:
            for item in result:
                print(f"{item.get('calendarId')}: {item.get('calendarName')} ({item.get('startDate') or '?'} ~ {item.get('endDate') or '?'})")
    elif args.command == "schedule-dictionaries":
        result = {"campuses": pk_get("/api/pk/campuses") or [], "faculties": pk_get("/api/pk/faculties") or []}
        print_json(result)
    elif args.command == "schedule-grades":
        result = pk_post("/api/pk/grades", {"calendarId": args.calendar_id})
        print_json(result)
    elif args.command == "schedule-majors":
        body = {"grade": args.grade}
        if args.calendar:
            body["calendarId"] = args.calendar
        print_json(pk_post("/api/pk/majors", body))
    elif args.command == "schedule-major-courses":
        result = pk_post("/api/pk/courses-by-major", {"calendarId": args.calendar_id, "grade": args.grade, "code": args.major_code}) or []
        print_json(result) if args.json else print_pk_major_courses(result)
    elif args.command == "schedule-optional-types":
        print_json(pk_post("/api/pk/optional-types", {"calendarId": args.calendar_id}))
    elif args.command == "schedule-nature-courses":
        result = pk_post("/api/pk/courses-by-nature", {"calendarId": args.calendar_id, "ids": args.nature_ids}) or []
        print_json(result) if args.json else print_pk_grouped_courses(result)
    elif args.command == "schedule-search":
        body = {"calendarId": args.calendar_id}
        for key, value in {
            "courseName": args.name,
            "courseCode": args.code,
            "teacherName": args.teacher,
            "teacherCode": args.teacher_code,
            "campus": args.campus,
            "faculty": args.faculty,
        }.items():
            if value:
                body[key] = value
        result = pk_post("/api/pk/course-search", body) or {}
        print_json(result) if args.json else print_pk_courses(result.get("courses") or [])
    elif args.command == "schedule-detail":
        body = {"calendarId": args.calendar_id}
        body["courseCode" if len(args.course_codes) == 1 else "courseCodes"] = args.course_codes[0] if len(args.course_codes) == 1 else args.course_codes
        result = pk_post("/api/pk/course-details", body)
        print_json(result) if args.json else print_pk_details(result)
    elif args.command == "schedule-time":
        result = pk_post("/api/pk/courses-by-time", {"calendarId": args.calendar_id, "day": args.day, "section": args.section}) or {}
        print_json(result) if args.json else print_pk_courses(result.get("courses") or [])
    elif args.command == "schedule-review":
        params = {"courseCode": args.course_code}
        if args.teacher:
            params["teacherName"] = args.teacher
        if args.calendar:
            params["calendarId"] = args.calendar
        if args.class_id:
            params["teachingClassId"] = args.class_id
        result = pk_get("/api/pk/course-review-brief", params) or {}
        print_json(result) if args.json else print(
            f"courseId={result.get('courseId')} | {result.get('courseName')} | {result.get('teacherName')} | "
            f"评分 {rating_text(result.get('ratingAvg'))} | {result.get('reviewCount', 0)} 条评价 | "
            f"https://f.yourtj.de/courses/{result.get('courseId')}"
        )
    elif args.command == "schedule-latest":
        print_json(pk_get("/api/pk/latest-update"))
    elif args.command == "schedule-section-times":
        print_json(pk_get("/api/pk/section-times"))


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        handle_command(args)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
