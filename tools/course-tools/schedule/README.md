# 同济大学教务系统课表导出工具

本工具用于从同济大学一系统教务网拉取完整的全校排课大表，并提供本地缓存和关键词查询。YourTJ Hub 的公开排课高级搜索最多返回 100 门，适合交互查询；完整快照使用本工具。免登录查询可使用 `D:\Antigravity-Hub\工具脚本\选课点评助手\query_yourtj.py schedule-*`。

## 运行环境

- Python 3.8 或更高版本，仅使用标准库，无需安装第三方 Python 包。
- 联网拉取前，需在 Firefox 登录 `https://1.tongji.edu.cn`；脚本读取 Firefox 的一系统本地存储和 Cookie。
- 已有 `.cache` 缓存时，列学期、格式转换和本地查询可不读取在线登录态。
- 可通过统一入口调用：`python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule <export|query> <参数>`。

---

## 🚀 命令行用法

进入脚本目录：
```powershell
cd "D:\Antigravity-Hub\工具脚本\同济课表导出"
```

### 1. 查询所有学期的 ID 映射
用于获取各个学期对应的 `calendarId`（优先读取本地学期列表缓存）：
```powershell
python export_schedule.py list-semesters
```
如果需要**强行联网更新**学期列表，请加 `--refresh`：
```powershell
python export_schedule.py list-semesters --refresh
```

### 2. 导出指定学期的课表
将指定学期的全校排课数据导出为 CSV 或 JSON（优先读取本地原始数据缓存以实现秒级转换）：
```powershell
# 导出大三上学期（ID: 122）课表为 CSV（默认格式）
python export_schedule.py export -c 122 -f csv

# 导出大三上学期（ID: 122）课表为 JSON
python export_schedule.py export -c 122 -f json
```

### 3. 自定义输出路径
```powershell
python export_schedule.py export -c 122 -f csv -o "D:\MyFolder\2026_1_schedule.csv"
```

### 4. 强制联网重新下载

若教务网排课信息发生变动，可加 `--refresh` 重新联网分页拉取：

```powershell
python export_schedule.py export -c 122 -f csv --refresh
```

不指定 `-o` 时，导出文件保存为 `.cache\tongji_<学期ID>_schedule.csv` 或 `.json`。

## 本地课表查询

`query_schedule.py` 查询导出的 CSV，支持 2024 级相对学期名称或直接使用 `calendarId`：

```powershell
python query_schedule.py --show-semesters
python query_schedule.py 大三上 数据库
python query_schedule.py 122 朱宏明
```

查询范围包括课程名称、课程代码、教师和排课信息。关键词包含空格时需要使用引号。目标 CSV 不存在时，查询脚本会自动调用 `export_schedule.py`；此时需要有效的一系统 Firefox 登录态。

也可从统一入口调用：

```powershell
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule export -c 122 -f csv
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule query 大三上 数据库
```

---

## ⚙️ 本地缓存机制说明

为了最大程度保护账号鉴权凭证不被频繁请求触发风控，脚本会自动在本地持久保存缓存文件：
* **学期映射列表缓存**：`D:\Antigravity-Hub\工具脚本\同济课表导出\.cache\semesters_cache.json`
* **原始全校排课缓存**：`D:\Antigravity-Hub\工具脚本\同济课表导出\.cache\tongji_[学期ID]_raw.json`

---

## 📡 课表拉取底层 API 说明

以下为该导出工具底层的网络数据接口，用于后续维护和查阅：

### 1. 官方教务一系统源 (onesystem)
需带 Firefox 本地存储解析到的 `X-Token` ( sessionid ) 以及 `.tongji.edu.cn` 域下的 Session Cookie 进行安全鉴权。

* **接口 ①：拉取所有历史学期映射列表**
  * **请求方法**：`GET`
  * **请求路径**：`https://1.tongji.edu.cn/api/baseresservice/schoolCalendar/list`
  * **返回数据**：所有学期的 ID（`calendarId`，如 122）、学年年度和学期。

* **接口 ②：分页拉取全校排课大表**
  * **请求方法**：`POST` (Content-Type: `application/json`)
  * **请求路径**：`https://1.tongji.edu.cn/api/arrangementservice/manualArrange/page?profile`
  * **Payload 结构**：
    ```json
    {
      "pageNum_": 1,
      "pageSize_": 500,
      "condition": {
        "calendar": 122,
        "ids": [],
        "course": ""
      }
    }
    ```


