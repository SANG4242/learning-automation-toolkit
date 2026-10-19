# look 课程录播下载工具

下载同济大学 `look.tongji.edu.cn` 课程录播视频。

## 运行环境

- Python 3.8 或更高版本，查询与课件下载仅使用标准库。
- 在 Firefox 中登录 `https://look.tongji.edu.cn`，脚本自动读取 Firefox Cookie 和 token；所有命令当前都会先验证该登录信息。
- 视频下载需要系统可调用 `curl.exe`，并需要访问 look API 和视频服务器。
- 可通过统一入口调用：`python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" look <参数>`。

## 课程搜索机制与调用风险

1. **`search` 命令（推荐）**：匹配本地 `courses_cache.json`，同时尝试一次在线“我的选课”查询，再将结果去重展示。请求量较小，但需要有效的 Firefox 登录信息。
2. **`search-all` 命令**：调用 look 的课程搜索接口，返回范围以平台当前响应为准。
3. **`search-update` 命令**：使用 80 个线程探测指定 ID 区间并增量更新本地缓存。仅在需要更新缓存且已明确扫描范围时运行。
4. **`scan-search` 命令**：实时并发扫描指定号段。请求量较大，只在普通搜索未命中且确有需要时运行。

---

## 使用方式

本工具主要由 AI 调用，用户只需告诉 AI 要下载什么。

### 常用命令速查

```powershell
# 1. 列出所有自己已选的课程
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" list

# 2. 本地检索课程（整合已选与全校缓存，支持拼音/汉字模糊匹配课程名或教师名）
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" search 数据库
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" search 黄长水

# 3. 增量更新本地课程缓存（首次使用或每学期开学新号段产生时运行）
# 自动以上一次扫描最大 ID 为起点，增量扫描至 88500 并合并到本地缓存
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" search-update --max 88500
# 手动指定扫描起止区间
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" search-update --min 73890 --max 88500

# 4. 调用 look 课程搜索接口（结果范围以平台当前响应为准）
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" search-all 数据库

# 5. 查看课程所有课次（✓有录播 ✗无录播）
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" info <course_id>

# 6. 下载指定课程指定日期（支持以英文逗号分隔指定多个日期以实现批量下载，如 2026-05-20,2026-05-25）
# 下载前比较远端 Content-Length；不完整文件自动断点续传，临时网络错误自动重试
    python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" download <course_id> <日期>
# 示例：批量下载 5月20号和25号的录播
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" download 86038 2026-05-20,2026-05-25

# 7. 自定义输出目录和文件名（注意：自定义文件名仅对单文件下载有效）
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" download <course_id> <日期> -o <目录> --name <文件名.mp4>

# 8. 下载课件 PPT（全部课次，无课件的自动跳过）
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" ppt <course_id>

# 9. 根据 look 页面地址或 MP4 直链下载
python "D:\Antigravity-Hub\工具脚本\look课程录播\download_look.py" url <页面URL或MP4直链> -o <目录> --name <文件名.mp4>
```

### 缓存库增量更新与长效使用指南

* **什么是课程 ID 号段？**
  look 平台的课程 ID（`course_id`）是全局自增的整数。大一、大二、大三的课程 ID 会分布在不同区间。例如 2026 年春季学期（当前大二下学期）新产生的课程 ID 范围主要位于 `73890 ~ 88426`。
* **新学期开学如何更新？**
  当进入新学期或者发现有最新课程时，可以通过运行下述命令对新学期可能产生的新号段进行增量扫描：
  ```powershell
  python download_look.py search-update --max <新学期的估计最大ID>
  ```
  脚本会自动读取本地已有的最大课程 ID ＋ 1 作为本次扫描的起点，多线程探测到新的有效课程后，会自动增量写入 `courses_cache.json` 并刷新更新时间。

### 典型工作流

用户说：「下载数据库5月11号的录播」

AI 执行：
1. `search 数据库` → 本地检索到 course_id=86038 (来自本地缓存)
2. `download 86038 2026-05-11` → 下载视频到默认目录

用户说：「下载黄长水老师的高数课件 PPT」

AI 执行：
1. `search 黄长水` → 本地检索到 course_id=73234 (来自本地缓存)
2. `ppt 73234` → 自动开始下载该高数教学班的所有课件

## 默认输出

`D:\Antigravity-Hub\temp\语音转录\audio\`

文件名格式：`{课程名}_{日期}.mp4`，如 `数据库原理与应用_2026-05-11.mp4`

## 技术细节

### 下载完整性、断点续传与适用范围

- `download` 命令和 `url` 命令中的视频下载都会先发送 `HEAD`，用远端 `Content-Length` 与本地文件大小比较；相等才视为完整。
- 本地文件小于远端时，使用 `curl -C -` 从已有字节处继续下载；连接重置、超时等临时错误最多自动重试 8 次。
- 断点续传依赖目标视频服务器支持 HTTP Range。Look 当前视频服务器已验证返回 `Accept-Ranges: bytes`；如果其他直链服务器不支持 Range，`curl` 可能无法续传，脚本会报告失败。
- 这不是系统级能力，只影响 `download_look.py` 内调用 `download_video()` 的视频下载。`ppt` 使用单独的 API 和一次性写入逻辑，不使用该断点续传流程；其他下载脚本也不会自动获得此能力。
- 若服务器未提供 `Content-Length`，脚本仍会让 `curl` 尝试续传，但无法仅靠长度做最终完整性确认。

### 认证

1. Firefox cookies 中的 `_token` 是 PHP serialize 格式，需正则提取真实 token：
   ```
   raw: {i:0;s:6:"_token";i:1;s:64:"实际token值";}
   提取: re.search(r'i:\d+;s:\d+:"_token";i:\d+;s:\d+:"(.+?)";', decoded)
   ```
2. API 认证方式（任选其一即可）：
   - `Authorization: Bearer {token}`（从 cookie 提取的纯 token）
   - `Cookie: _token=...`（直接带原始 cookie）
   - 两者同时带也可以（脚本当前做法）
3. 视频直链（`/play/1/newdefault/...mp4`）无需任何认证，公开可下载

### 已验证可用的 API

**脚本使用中的：**

| API | 用途 |
|---|---|
| `GET /vlabpassportapi/v1/account-profile/course?page=1&pageSize=100` | 我的选课列表 |
| `GET /courseapi/v2/course/{id}` | 课程详情+所有课次+视频URL |
| `GET /courseapi/v2/course-live/search-live-course-list?need_time_quantum=1&unique_course=1&with_sub_data=1` | 全校课程搜索（824门，2.6MB） |
| `GET /userapi/v1/infosimple` | 当前用户信息 |
| `GET /vlabpassportapi/v1/account-profile/rcourse/export/download-sub-ppt?course_id=&sub_id=` | 下载课件PPT（返回PPTX二进制） |

**已验证可用但未集成：**

| API | 用途 | 实测备注 |
|---|---|---|
| `GET /vlabpassportapi/v1/account-profile/study` | 最近学习过的课程 | 仅返回最近2门 |
| `GET /vlabpassportapi/v1/account-profile/course-note` | 课程笔记列表 | 可用 |
| `GET /vlabpassportapi/v1/account-profile/export-note?course_id=` | 导出笔记为文件 | 返回二进制 |
| `GET /vlabpassportapi/v1/account-profile/exam-score?course_id=` | 各课程成绩 | 实测全部为0（未出分） |
| `GET /vlabpassportapi/v1/course/source/study/record/{id}` | 课程学习记录 | 实测返回空 |
| `GET /vlabpassportapi/v1/course/source/study/stats/{id}` | 全班学习统计 | 实测返回空 |
| `GET /vlabpassportapi/v1/account-profile/rcourse/export/download-sub-trans` | 下载转录文本 | 实测全部"暂无课件内容"（平台未启用） |
| `GET /courseapi/v2/intelligent-summary/detail?course_id=&sub_id=` | AI 智能摘要 | 实测全部"没有相应数据"（平台未启用） |
| `GET /courseapi/v3/multi-search/get-course-detail?course_id=` | 课程详情（按年月日分组） | 可用 |

**已确认不可用（403 Auth Forbidden）：**

弹幕(`/courseapi/v2/barrage/`)、论坛(`/courseapi/v2/forum/`)、签到(`/courseapi/v2/checkin/`)、课件列表(`/courseapi/v2/courseware/`) — 这批 API 的认证机制与 Bearer token 不同，GET/POST 均 403。毕业生回看(`/courseapi/v3/graduate/get-play-data`) 返回"非毕业生"。

**注意**：带 `/courseapi/vlabpassportapi/` 前缀的会 403，去掉 `courseapi/` 前缀用 `/vlabpassportapi/` 才能访问。

### 前端 JS 逆向方法

如需探索更多 API，方法如下：

1. **下载前端代码**：
   ```powershell
   curl.exe -o app.js "https://look.tongji.edu.cn/static/js/app.7c9490fbcaa4883a0cda.1775805638916.js"
   ```
   （URL 可能变化，从 `view-source:https://look.tongji.edu.cn` 的 `<script>` 标签获取最新路径）

2. **搜索 API 路径**：JS 中 API 调用格式为 `"./courseapi/..."` 或 `"./vlabpassportapi/..."`
   ```python
   import re
   paths = re.findall(r'"(\./[a-zA-Z]+api/[^"]+)"', js_content)
   ```

3. **搜索特定功能**：搜索关键词找到相关代码上下文
   - 视频相关：`video`, `play`, `stream`, `record`, `replay`
   - 认证相关：`Authorization`, `Bearer`, `getToken`, `_token`
   - 下载相关：`download`, `export`

4. **API 分类**：从 JS 中提取的约 130 个 API 分为：课程信息(66)、视频媒体(9)、用户(29)、下载(8)、弹幕(11)、论坛(14)、签到(5)、其他(28)

5. **测试 API**：用 Python 脚本带 Bearer token 测试，注意两点：
   - 前缀问题：JS 中写的 `./courseapi/vlabpassportapi/...` 实际要用 `/vlabpassportapi/...`
   - 全校搜索 API 数据量大（2.6MB），不要传 `pageSize=1000`（会 502），不传 pageSize 让服务端默认

