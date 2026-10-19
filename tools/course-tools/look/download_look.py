"""
同济大学 look.tongji.edu.cn 课程录播下载工具

前置：Firefox 已登录 look.tongji.edu.cn；视频下载还需要系统可调用 curl.exe。

命令速查：
  list                              列出你的所有选课（含 course_id）
  search <关键词>                   匹配本地缓存，并尝试合并一次在线“我的选课”查询
  search-update --max <最大ID>      多线程增量扫描并更新本地课程缓存大表（可加 --min）
  search-all <关键词>               调用 look 课程搜索接口（范围以平台响应为准）
  scan-search <关键词>              在线并发扫描课程 ID（可加 --min/--max，请谨慎使用）
  info <course_id>                  列出该课程所有课次（✓有录播 ✗无录播）
  download <course_id> [日期]       下载录播视频（支持以英文逗号分隔指定多个日期，如 2026-05-20,2026-05-25），不填则下载全部
  ppt <course_id> [日期]            下载课件PPT，不填日期则尝试下载全部
  url <页面URL 或 .mp4直链>          直接从 URL 下载

可选参数：
  -o, --output <目录>               自定义输出目录（download / ppt / url）
  --name <文件名>                   自定义文件名（仅 download / url）

典型用法：
  python download_look.py search 王冬青                  # 优先在本地已缓存的大表里匹配王冬青老师的课
  python download_look.py search-update --max 88500     # 自动从缓存最大 ID 起，增量扫荡至 88500 并更新缓存
  python download_look.py info 86038                    # 查看该课程的所有课次
  python download_look.py download 86038 2026-05-11     # 下载5月11号录播
  python download_look.py download 86038 2026-05-11,2026-05-13  # 批量下载5月11号和13号的录播
  python download_look.py ppt 86038                     # 下载所有有课件的PPT

"""
import sqlite3, os, sys, json, re, subprocess, time, webbrowser
import urllib.request, urllib.parse, urllib.error
from datetime import datetime
from pathlib import Path

BASE_URL = "https://look.tongji.edu.cn"
DATA_DIR = Path(os.environ.get("LEARNING_TOOLS_DATA_DIR", str(Path(__file__).resolve().parents[3] / ".local")))
DEFAULT_OUTPUT = os.environ.get("LEARNING_AUDIO_DIR", str(DATA_DIR / "audio"))


# ============================================================
# 认证工具函数与自动唤起登录
# ============================================================

def get_firefox_cookies(validate=False, report=False):
    """只读查询 Firefox Cookie 快照，包含 WAL 中已提交的数据。"""
    profiles_dir = Path(os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles"))
    if not profiles_dir.is_dir():
        if report:
            print("  [凭证读取] 未找到 Firefox 配置目录", flush=True)
        return {}
    candidate_dbs = []
    for cookie_file in profiles_dir.glob("*/cookies.sqlite"):
        try:
            modified = cookie_file.stat().st_mtime
            wal_file = Path(str(cookie_file) + "-wal")
            if wal_file.exists():
                modified = max(modified, wal_file.stat().st_mtime)
            candidate_dbs.append((modified, cookie_file))
        except OSError:
            continue
    candidate_dbs.sort(key=lambda item: item[0], reverse=True)

    for _, cookie_file in candidate_dbs:
        try:
            conn = sqlite3.connect(cookie_file.as_uri() + "?mode=ro", uri=True, timeout=2)
            try:
                rows = conn.execute(
                    "SELECT name, value, originAttributes FROM moz_cookies "
                    "WHERE host IN (?, ?, ?, ?) AND (expiry = 0 OR expiry > ?) "
                    "AND path = '/' ORDER BY length(host), lastAccessed",
                    ("tongji.edu.cn", ".tongji.edu.cn", "look.tongji.edu.cn",
                     ".look.tongji.edu.cn", int(time.time())),
                ).fetchall()
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as error:
            if report:
                print(f"  [凭证读取] 配置 {cookie_file.parent.name}：{type(error).__name__}", flush=True)
            continue
        contexts = {}
        for name, value, origin in rows:
            contexts.setdefault(origin, {})[name] = value
        for origin, cookies in contexts.items():
            token = extract_token(cookies)
            if not token:
                continue
            if validate and not verify_token(cookies, token, report=report):
                continue
            if report:
                context = origin or "默认容器"
                print(f"  [凭证读取] 配置 {cookie_file.parent.name}，{context}", flush=True)
            return cookies
    if report:
        print("  [凭证读取] 未找到可用的 Look 凭证", flush=True)
    return {}


def extract_token(cookies):
    """从 _token cookie 中提取真实 token（PHP serialize 格式）"""
    raw = cookies.get("_token", "")
    decoded = urllib.parse.unquote(raw)
    m = re.search(r'i:\d+;s:\d+:"_token";i:\d+;s:\d+:"(.+?)";', decoded)
    return m.group(1) if m else decoded


def verify_token(cookies, token, timeout=5, report=False):
    """验证当前凭证是否有效"""
    url = f"{BASE_URL}/userapi/v1/infosimple"
    headers = {
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        params = data.get("params")
        valid = (
            data.get("code") == 200
            and isinstance(params, dict)
            and params.get("id") is not None
        )
        if report and not valid:
            print("  [凭证验证] Look 接口未确认登录有效", flush=True)
        return valid
    except urllib.error.HTTPError as error:
        if report:
            print(f"  [凭证验证] HTTP {error.code}", flush=True)
    except (urllib.error.URLError, OSError):
        if report:
            print("  [凭证验证] 网络连接失败或超时", flush=True)
    except (ValueError, AttributeError):
        if report:
            print("  [凭证验证] 接口响应格式异常", flush=True)
    return False


def launch_firefox_and_wait(old_token=None, reason="登录凭证已失效", timeout=180):
    """自动拉起 Firefox 并阻塞轮询等待用户登录成功刷新凭证"""
    print("\n" + "=" * 80)
    print(f"【登录提示】{reason}！")
    print("正在自动调起 Firefox 浏览器打开 https://look.tongji.edu.cn ...")
    print("请在浏览器中完成登录（密码已自动填充，点击登录即可）。")
    print(f"脚本已暂停，正在等待凭证刷新（最长等待 {timeout} 秒，按 Ctrl+C 可取消）...")
    print("=" * 80 + "\n", flush=True)

    # 尝试调起系统 Firefox
    firefox_paths = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ]
    launched = False
    for fp in firefox_paths:
        if os.path.exists(fp):
            try:
                subprocess.Popen([fp, "https://look.tongji.edu.cn"])
                launched = True
                break
            except Exception:
                pass
    if not launched:
        webbrowser.open("https://look.tongji.edu.cn")

    start_time = time.time()
    last_print = 0
    while time.time() - start_time < timeout:
        time.sleep(2)
        elapsed = int(time.time() - start_time)
        report = elapsed // 10 > last_print
        if report:
            last_print = elapsed // 10
            print(f"  [等待登录] 已等待 {elapsed} 秒...", flush=True)

        new_cookies = get_firefox_cookies(validate=True, report=report)
        if new_cookies:
            new_token = extract_token(new_cookies)
            print("\n【登录成功】Look 接口已确认当前凭证有效！继续执行任务...\n", flush=True)
            return new_cookies, new_token

    print(f"\n【超时错误】等待登录超过 {timeout} 秒，未能检测到有效凭证，操作终止。")
    sys.exit(1)


def api_get(path, cookies, token, timeout=30, _auth_retried=False):
    """调用 Look API；403 时刷新凭证并重试一次。"""
    token = extract_token(cookies) or token
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    headers = {
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 403 and not _auth_retried:
            error.close()
            new_cookies, new_token = launch_firefox_and_wait(old_token=token, reason="HTTP 403 Forbidden - 登录凭证已失效")
            cookies.clear()
            cookies.update(new_cookies)
            return api_get(path, cookies, new_token, timeout=timeout, _auth_retried=True)
        raise


# ============================================================
# 缓存管理工具函数
# ============================================================

CACHE_FILE = os.environ.get("LEARNING_LOOK_CACHE", str(DATA_DIR / "look" / "courses_cache.json"))

def load_cache():
    """读取本地课程缓存"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_updated": "", "courses": {}}


def save_cache(cache_data):
    """保存本地课程缓存"""
    try:
        Path(CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"警告：无法写入本地缓存文件: {e}")


def scan_and_update_cache(cookies, token, min_id=None, max_id=None):
    """增量扫描指定 ID 区间的有效课程并合并到本地缓存"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    cache = load_cache()
    existing_courses = cache.get("courses", {})
    
    # 自动推导起点
    if min_id is None:
        if existing_courses:
            max_exist = max([int(cid) for cid in existing_courses.keys() if cid.isdigit()] + [70000])
            min_id = max_exist + 1
        else:
            min_id = 70000
        print(f"  [缓存更新] 自动设置扫描起点为: {min_id}")
        
    if max_id is None:
        print("错误：必须提供结束扫描 ID 参数 --max <最大ID>")
        return False
        
    if min_id > max_id:
        print(f"错误：起始 ID ({min_id}) 大于结束 ID ({max_id})，无需更新。")
        return False
        
    id_list = list(range(min_id, max_id + 1))
    print(f"  [缓存更新] 增量扫描区间: {min_id} ~ {max_id} (共 {len(id_list)} 个 ID)")
    
    results = {}
    completed = 0
    total = len(id_list)
    
    def scan_single_id(cid):
        url = f"{BASE_URL}/courseapi/v2/course/{cid}"
        headers = {
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                info = data.get("result", {}).get("data", {})
                title = info.get("title", "")
                if title:
                    teachers = info.get("teachers", [])
                    teacher_names = []
                    for t in teachers:
                        if isinstance(t, dict):
                            name = t.get("realname")
                            if name:
                                teacher_names.append(name)
                        elif isinstance(t, str):
                            teacher_names.append(t)
                    return {
                        "id": str(cid),
                        "title": title,
                        "teacher": ", ".join(teacher_names) if teacher_names else "未知"
                    }
        except Exception:
            pass
        return None

    print("  [缓存更新] 正在执行多线程并发扫描...")
    with ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(scan_single_id, cid): cid for cid in id_list}
        for future in as_completed(futures):
            completed += 1
            if completed % 1000 == 0:
                print(f"  [缓存更新] 扫描进度: {completed}/{total} ({(completed/total)*100:.1f}%)")
            
            res = future.result()
            if res:
                cid = res["id"]
                results[cid] = {
                    "title": res["title"],
                    "teacher": res["teacher"]
                }
                print(f"  [★ 扫得有效课程] ID: {cid:>6s} | 教师: {res['teacher']:<10s} | 课程: {res['title']}")
                
    # 合并到现有缓存
    if results:
        existing_courses.update(results)
        cache["courses"] = existing_courses
        cache["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_cache(cache)
        print(f"\n[缓存更新完成] 本次新增 {len(results)} 门课程，本地缓存库共有 {len(existing_courses)} 门课程。")
    else:
        print("\n[缓存更新完成] 本次扫描未发现新课程。")
    return True


# ============================================================
# 业务逻辑函数
# ============================================================

def list_courses(cookies, token):
    """获取用户选的所有课程，返回 [{id, title, teacher}, ...]"""
    data = api_get(
        "/vlabpassportapi/v1/account-profile/course?page=1&pageSize=100",
        cookies, token,
    )
    raw = data.get("params", {}).get("result", {}).get("data", [])
    return [
        {"id": str(c["Id"]), "title": c["Title"], "teacher": c["Teacher"]}
        for c in raw
    ]


def search_course(courses, keyword):
    """按关键词模糊搜索课程（匹配课程名或教师名）"""
    return [c for c in courses if keyword in c["title"] or keyword in c["teacher"]]


def search_all_courses(keyword, cookies, token):
    """搜索全校所有课程（按课程名或教师名），返回去重后的列表"""
    data = api_get(
        "/courseapi/v2/course-live/search-live-course-list"
        "?need_time_quantum=1&unique_course=1&with_sub_data=1",
        cookies, token, timeout=60,
    )
    seen = set()
    results = []
    for slot in data.get("list", []):
        for course in slot.get("list", []):
            teacher = course.get("teacher_search", "")
            title = course.get("title", "")
            cid = course.get("id", "")
            if keyword in title or keyword in teacher:
                if cid not in seen:
                    seen.add(cid)
                    results.append({
                        "id": cid, "title": title, "teacher": teacher,
                        "room": course.get("room_name", ""),
                    })
    return results


def scan_search_courses(keyword, cookies, token, min_id=None, max_id=None):
    """使用多线程高并发扫描课程详情 API，实现全校全局搜索"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # 确定扫描的 ID 范围
    if min_id is not None and max_id is not None:
        id_list = list(range(min_id, max_id + 1))
        print(f"  [扫描器] 使用手动指定的 ID 扫描范围: {min_id} ~ {max_id}")
    else:
        # 自动探测
        try:
            courses = list_courses(cookies, token)
            if courses:
                ids = [int(c["id"]) for c in courses if c["id"].isdigit()]
                if ids:
                    calc_min = max(1000, min(ids) - 8000)
                    calc_max = max(ids) + 2000
                    id_list = list(range(calc_min, calc_max + 1))
                    print(f"  [扫描器] 自动检测到选课 ID，本学期扫描区间: {calc_min} ~ {calc_max} (共 {len(id_list)} 个 ID)")
                else:
                    raise ValueError
            else:
                raise ValueError
        except Exception:
            # 兜底默认值
            id_list = list(range(78000, 88000))
            print(f"  [扫描器] 无法自动估算范围，使用默认兜底扫描区间: 78000 ~ 88000 (共 {len(id_list)} 个 ID)")

    results = []
    seen = set()
    
    def scan_single_id(cid):
        url = f"{BASE_URL}/courseapi/v2/course/{cid}"
        headers = {
            "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                body = response.read().decode("utf-8")
                if keyword in body:
                    data = json.loads(body)
                    info = data.get("result", {}).get("data", {})
                    title = info.get("title", "")
                    teachers = info.get("teachers", [])
                    
                    teacher_names = []
                    for t in teachers:
                        if isinstance(t, dict):
                            name = t.get("realname")
                            if name:
                                teacher_names.append(name)
                        elif isinstance(t, str):
                            teacher_names.append(t)
                    
                    if keyword in title or any(keyword in name for name in teacher_names):
                        # 健壮解析教室（content 可能是 dict 或者是 str 形式 of JSON）
                        content = info.get("content", {})
                        room = ""
                        if isinstance(content, dict):
                            room = content.get("address", "") or ""
                        elif isinstance(content, str):
                            if content.strip().startswith("{"):
                                try:
                                    content_json = json.loads(content)
                                    if isinstance(content_json, dict):
                                        room = content_json.get("address", "") or ""
                                except Exception:
                                    pass
                            if not room:
                                room = content
                                
                        return {
                            "id": str(cid),
                            "title": title,
                            "teacher": ", ".join(teacher_names) if teacher_names else "未知",
                            "room": room
                        }
        except Exception:
            pass
        return None

    print("  [扫描器] 正在执行多线程并发扫描...")
    completed = 0
    total = len(id_list)
    
    with ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(scan_single_id, cid): cid for cid in id_list}
        for future in as_completed(futures):
            completed += 1
            if completed % 1000 == 0:
                print(f"  [扫描器] 扫描进度: {completed}/{total} ({(completed/total)*100:.1f}%)")
            
            res = future.result()
            if res:
                cid = res["id"]
                if cid not in seen:
                    seen.add(cid)
                    results.append(res)
                    print(f"  [★ 命中] ID: {cid:>6s} | 教师: {res['teacher']:<10s} | 课程: {res['title']}")
    if results:
        try:
            cache = load_cache()
            existing_courses = cache.get("courses", {})
            updated = False
            for res in results:
                cid = res["id"]
                if cid not in existing_courses:
                    existing_courses[cid] = {
                        "title": res["title"],
                        "teacher": res["teacher"]
                    }
                    updated = True
            if updated:
                cache["courses"] = existing_courses
                cache["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_cache(cache)
                print(f"  [缓存自动更新] 已将命中的 {len(results)} 门有效课程保存合并至本地缓存。")
            else:
                print(f"  [缓存状态] 命中的 {len(results)} 门课程均已存在于本地缓存中，无需更新。")
        except Exception as e:
            print(f"  [缓存自动更新警告] 自动写入缓存失败: {e}")
            
    return results


def get_subjects(course_id, cookies, token):
    """获取课程所有课次及视频链接，返回 [{id, title, date, video_url, duration}, ...]"""
    data = api_get(f"/courseapi/v2/course/{course_id}", cookies, token)
    subjects_raw = data["result"]["data"].get("subject", [])
    course_title = data["result"]["data"].get("title", "")
    results = []
    for sub in subjects_raw:
        content = sub.get("content", {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                content = {}
        if not isinstance(content, dict):
            content = {}
        # 提取视频 URL
        video_url = ""
        playback = content.get("playback", {})
        if isinstance(playback, dict):
            video_url = playback.get("url", "")
        if not video_url:
            save_pb = content.get("save_playback", {})
            if isinstance(save_pb, dict):
                video_url = save_pb.get("contents", "")
        # 提取日期（从标题中解析，格式如 "2026-05-11第1-2节"）
        title = sub.get("title", "")
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", title)
        date_str = date_match.group(1) if date_match else ""
        results.append({
            "id": sub["id"],
            "title": title,
            "date": date_str,
            "status": str(sub.get("status", "")),
            "video_url": video_url if video_url.startswith("http") else "",
            "duration": sub.get("duration", ""),
        })
    return results, course_title


def parse_livingroom_url(url):
    """从 livingroom 页面 URL 中提取 course_id 和 sub_id"""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    course_id = params.get("course_id", [None])[0]
    sub_id = params.get("sub_id", [None])[0]
    return course_id, sub_id


def download_ppt(course_id, sub_id, cookies, token, output_path):
    """下载指定课次的课件 PPT，返回是否成功"""
    url = (
        f"/vlabpassportapi/v1/account-profile/rcourse/export/download-sub-ppt"
        f"?course_id={course_id}&sub_id={sub_id}"
    )
    full_url = f"{BASE_URL}{url}"
    headers = {
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(full_url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = resp.read()
    except Exception as e:
        print(f"  请求失败: {e}")
        return False
    # 判断是否为有效的 PPTX 文件（ZIP 格式 magic bytes）
    if len(data) < 100:
        try:
            j = json.loads(data)
            if j.get("code") == 2002:
                return False  # 暂无课件内容，静默跳过
            print(f"  API 返回: {j.get('msg', '未知错误')}")
        except (json.JSONDecodeError, TypeError):
            pass
        return False
    # 检查 ZIP magic bytes
    if data[:4] != b'PK\x03\x04':
        try:
            j = json.loads(data)
            print(f"  API 返回: {j.get('msg', '未知响应')}")
        except (json.JSONDecodeError, TypeError):
            print(f"  未知响应（{len(data)} bytes）")
        return False
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    size_kb = len(data) / 1024
    print(f"  完成（{size_kb:.0f}KB）: {os.path.basename(output_path)}")
    return True


def remote_content_length(video_url):
    """读取远端视频总大小；失败时返回 0，由 curl 负责续传。"""
    try:
        req = urllib.request.Request(video_url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def is_tongji_intranet_available(host="192.168.155.158", port=443, timeout=1.0):
    """检测当前网络是否可直接访问同济内网 Look 服务器"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        res = sock.connect_ex((host, port))
        sock.close()
        return res == 0
    except Exception:
        return False


def download_video(video_url, output_path):
    """用 curl.exe 下载视频，按远端长度校验并支持断点续传。"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    remote_size = remote_content_length(video_url)
    local_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    if remote_size > 0 and local_size == remote_size:
        print(f"  跳过（文件完整，{local_size / 1024 / 1024:.1f}MB）: {os.path.basename(output_path)}")
        return True
    if local_size > 0:
        if remote_size > 0:
            print(
                f"  继续下载（本地 {local_size / 1024 / 1024:.1f}MB / "
                f"远端 {remote_size / 1024 / 1024:.1f}MB）"
            )
        else:
            print(f"  继续下载（本地已有 {local_size / 1024 / 1024:.1f}MB）")
    cmd = [
        "curl.exe", "-L",
        "-o", output_path,
        "-C", "-",
        "--retry", "8",
        "--retry-all-errors",
        "--retry-delay", "3",
        "--connect-timeout", "30",
    ]
    if "look.tongji.edu.cn" in video_url and is_tongji_intranet_available():
        print("  [网络探测] 检测到同济内网直连可用，启用内网 IP 强制解析并跳过代理")
        cmd.extend([
            "--resolve", "look.tongji.edu.cn:443:192.168.155.158",
            "--noproxy", "*",
        ])
    cmd.extend([
        "--progress-bar",
        video_url,
    ])
    result = subprocess.run(cmd)
    final_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    if result.returncode != 0:
        print(f"  下载失败（返回码: {result.returncode}，当前 {final_size / 1024 / 1024:.1f}MB）")
        return False
    if remote_size > 0 and final_size != remote_size:
        print(
            f"  下载未完成（本地 {final_size / 1024 / 1024:.1f}MB / "
            f"远端 {remote_size / 1024 / 1024:.1f}MB）"
        )
        return False
    print(f"  完成（{final_size / 1024 / 1024:.1f}MB）: {os.path.basename(output_path)}")
    return True


# ============================================================
# 初始化与 CLI 入口
# ============================================================

def init_auth():
    """验证 Firefox 中的 Look 凭证，必要时等待重新登录。"""
    cookies = get_firefox_cookies(validate=True, report=True)
    if cookies:
        return cookies, extract_token(cookies)
    return launch_firefox_and_wait(reason="未检测到有效的 Look 登录凭证")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    cookies, token = init_auth()

    # --- list: 列出所有选课 ---
    if cmd == "list":
        courses = list_courses(cookies, token)
        print(f"你的选课（共 {len(courses)} 门）：")
        for c in courses:
            print(f"  ID: {c['id']:>6s}  教师: {c['teacher']:<8s}  课程: {c['title']}")

    # --- search: 本地模糊匹配查询课程（整合我的选课与本地缓存大表） ---
    elif cmd == "search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        if not keyword:
            print("用法: download_look.py search <关键词>")
            sys.exit(1)
        
        # 1. 在线获取“我的选课”（如果有网的话）
        my_courses = []
        try:
            my_courses = list_courses(cookies, token)
        except Exception:
            pass
        
        # 2. 读取本地缓存
        cache = load_cache()
        cached_courses = cache.get("courses", {})
        
        matched_my = search_course(my_courses, keyword)
        matched_cache = []
        for cid, info in cached_courses.items():
            if keyword in info["title"] or keyword in info["teacher"]:
                matched_cache.append({
                    "id": cid,
                    "title": info["title"],
                    "teacher": info["teacher"]
                })
                
        # 3. 合并与去重展示
        seen_ids = set()
        all_matches = []
        
        # 优先加入我已选的课程
        for c in matched_my:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                all_matches.append({"id": c["id"], "title": c["title"], "teacher": c["teacher"], "type": "我的选课"})
                
        for c in matched_cache:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                all_matches.append({"id": c["id"], "title": c["title"], "teacher": c["teacher"], "type": "本地缓存"})
                
        if all_matches:
            print(f"模糊搜索关键词 '{keyword}'，共命中 {len(all_matches)} 门课：")
            for c in all_matches:
                print(f"  ID: {c['id']:>6s}  教师: {c['teacher']:<10s}  课程: {c['title']} ({c['type']})")
        else:
            print(f"本地缓存与我的选课中均未找到包含 '{keyword}' 的课程。")
            print("若需在线搜索新学期课程，可进行缓存更新。用法：")
            print("  python download_look.py search-update --max <最大扫描ID> [--min 最小扫描ID]")

    # --- search-update: 增量并发探测并更新本地缓存大表 ---
    elif cmd == "search-update":
        min_id = None
        max_id = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--min" and i + 1 < len(sys.argv):
                try:
                    min_id = int(sys.argv[i+1])
                except ValueError:
                    pass
                i += 2
            elif sys.argv[i] == "--max" and i + 1 < len(sys.argv):
                try:
                    max_id = int(sys.argv[i+1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
                
        if max_id is None:
            print("用法: download_look.py search-update --max <最大扫描ID> [--min 最小扫描ID]")
            sys.exit(1)
            
        print("开始更新本地课程缓存大表...")
        scan_and_update_cache(cookies, token, min_id, max_id)

    # --- search-all: 搜索全校所有课程 ---
    elif cmd == "search-all":
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        if not keyword:
            print("用法: download_look.py search-all <关键词/教师名>")
            sys.exit(1)
        print(f"在全校课程中搜索 '{keyword}'...")
        matched = search_all_courses(keyword, cookies, token)
        if matched:
            print(f"命中 {len(matched)} 门课：")
            for c in matched:
                room = f"  教室: {c['room']}" if c.get('room') else ""
                print(f"  ID: {c['id']:>6s}  教师: {c['teacher']:<10s}  课程: {c['title']}{room}")
        else:
            print(f"全校未找到包含 '{keyword}' 的课程")

    # --- scan-search: 全局扫描搜索全校课程 ---
    elif cmd == "scan-search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        if not keyword:
            print("用法: download_look.py scan-search <关键词/教师名> [--min 最小ID] [--max 最大ID]")
            sys.exit(1)
            
        min_id = None
        max_id = None
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--min" and i + 1 < len(sys.argv):
                try:
                    min_id = int(sys.argv[i+1])
                except ValueError:
                    pass
                i += 2
            elif sys.argv[i] == "--max" and i + 1 < len(sys.argv):
                try:
                    max_id = int(sys.argv[i+1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
                
        print(f"在全校范围内扫描搜索 '{keyword}'...")
        matched = scan_search_courses(keyword, cookies, token, min_id, max_id)
        if matched:
            print(f"\n[扫描完成] 命中 {len(matched)} 门课：")
            for c in matched:
                room = f"  教室: {c['room']}" if c.get('room') else ""
                print(f"  ID: {c['id']:>6s}  教师: {c['teacher']:<10s}  课程: {c['title']}{room}")
        else:
            print(f"\n[扫描完成] 全校未找到包含 '{keyword}' 的课程")

    # --- info: 查看课程所有课次 ---
    elif cmd == "info":
        course_id = sys.argv[2] if len(sys.argv) > 2 else ""
        if not course_id:
            print("用法: download_look.py info <course_id>")
            sys.exit(1)
        subjects, title = get_subjects(course_id, cookies, token)
        print(f"课程: {title}（ID: {course_id}，共 {len(subjects)} 课次）")
        for s in subjects:
            has_video = "✓" if s["video_url"] else "✗"
            dur = f"{int(s['duration'])//60}分" if s["duration"] else ""
            print(f"  [{has_video}] {s['title']}  {dur}")

    # --- download: 下载指定课程指定日期的视频 ---
    elif cmd == "download":
        course_id = sys.argv[2] if len(sys.argv) > 2 else ""
        date_filter = sys.argv[3] if len(sys.argv) > 3 else ""
        # 解析可选参数
        output_dir = DEFAULT_OUTPUT
        custom_name = ""
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] in ("-o", "--output") and i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                custom_name = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        if not course_id:
            print("用法: download_look.py download <course_id> [日期] [-o 目录] [--name 文件名]")
            sys.exit(1)
        subjects, title = get_subjects(course_id, cookies, token)
        # 筛选
        targets = subjects
        if date_filter:
            filter_dates = [d.strip() for d in date_filter.split(",") if d.strip()]
            targets = [s for s in subjects if any(fd in s["date"] for fd in filter_dates)]
        targets = [s for s in targets if s["video_url"]]
        if not targets:
            print(f"未找到匹配的录播（课程: {title}, 日期筛选: {date_filter or '无'}）")
            available = [s for s in subjects if s["video_url"]]
            if available:
                print("可用的录播日期：")
                for s in available:
                    print(f"  {s['date']}  {s['title']}")
            sys.exit(1)
        for s in targets:
            if custom_name:
                filename = custom_name
            else:
                filename = f"{title}_{s['date']}.mp4"
            filepath = os.path.join(output_dir, filename)
            print(f"下载: {s['title']} -> {filepath}")
            download_video(s["video_url"], filepath)

    # --- ppt: 下载课件 PPT ---
    elif cmd == "ppt":
        course_id = sys.argv[2] if len(sys.argv) > 2 else ""
        if not course_id:
            print("用法: download_look.py ppt <course_id> [日期] [-o 目录]")
            sys.exit(1)
        # 解析可选参数（日期和输出目录）
        date_filter = ""
        output_dir = DEFAULT_OUTPUT
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] in ("-o", "--output") and i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            elif not date_filter and re.match(r"\d{4}-\d{2}-\d{2}", sys.argv[i]):
                date_filter = sys.argv[i]
                i += 1
            else:
                i += 1
        subjects, title = get_subjects(course_id, cookies, token)
        targets = subjects
        if date_filter:
            targets = [s for s in subjects if date_filter in s["date"]]
        if not targets:
            print(f"未找到匹配的课次（课程: {title}, 日期筛选: {date_filter or '无'}）")
            sys.exit(1)
        downloaded = 0
        skipped = 0
        for s in targets:
            filename = f"{title}_{s['date']}_课件.pptx"
            filepath = os.path.join(output_dir, filename)
            if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                size_kb = os.path.getsize(filepath) / 1024
                print(f"  跳过（已存在，{size_kb:.0f}KB）: {os.path.basename(filepath)}")
                skipped += 1
                continue
            if download_ppt(course_id, str(s["id"]), cookies, token, filepath):
                downloaded += 1
            else:
                skipped += 1
        print(f"\nPPT 下载完成: {downloaded} 个下载, {skipped} 个跳过（无课件或已存在）")

    # --- url: 从页面 URL 解析并下载 ---
    elif cmd == "url":
        page_url = sys.argv[2] if len(sys.argv) > 2 else ""
        if not page_url:
            print("用法: download_look.py url <页面URL> [-o 目录] [--name 文件名]")
            sys.exit(1)
        output_dir = DEFAULT_OUTPUT
        custom_name = ""
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] in ("-o", "--output") and i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                custom_name = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        # 如果是直接的 mp4 链接
        if page_url.endswith(".mp4"):
            filename = custom_name or os.path.basename(page_url)
            filepath = os.path.join(output_dir, filename)
            print(f"直接下载: {filepath}")
            download_video(page_url, filepath)
        else:
            course_id, sub_id = parse_livingroom_url(page_url)
            if not course_id:
                print(f"无法从 URL 中提取 course_id: {page_url}")
                sys.exit(1)
            subjects, title = get_subjects(course_id, cookies, token)
            if sub_id:
                targets = [s for s in subjects if str(s["id"]) == sub_id and s["video_url"]]
            else:
                targets = [s for s in subjects if s["video_url"]]
            if not targets:
                print(f"未找到对应的录播视频（course_id={course_id}, sub_id={sub_id}）")
                sys.exit(1)
            for s in targets:
                filename = custom_name or f"{title}_{s['date']}.mp4"
                filepath = os.path.join(output_dir, filename)
                print(f"下载: {s['title']} -> {filepath}")
                download_video(s["video_url"], filepath)

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()


