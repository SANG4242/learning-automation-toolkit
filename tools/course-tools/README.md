# 同济课程工具统一入口

`course_tools.py` 统一调用 YourTJ 课程查询、全校课表导出与查询、look 录播下载。它只负责定位脚本、透传参数和退出码，具体功能仍由原工具实现。

## 公开仓库入口

本说明保留原统一入口的全部命令和调用规则。仓库内使用 `python tools/course-tools/course_tools.py` 替换下文的原Hub绝对路径；底层工具分别位于 [look](look/README.md)、[yourtj](yourtj/README.md)、[schedule](schedule/README.md)，功能与参数保留。

录播默认输出由 `LEARNING_AUDIO_DIR`／`LEARNING_TOOLS_DATA_DIR` 决定；课程缓存默认在独立 `.local/look/`。课表缓存由 `LEARNING_SCHEDULE_CACHE` 配置，默认本工具的 `.cache/`；点评输出由 `LEARNING_COURSE_REVIEWS_DIR` 配置。脚本不向原Hub目录写入。

## 运行环境

- Python 3.8 或更高版本。
- YourTJ 查询需要联网，无需登录。
- 课表联网抓取需要在 Firefox 登录 `https://1.tongji.edu.cn`；已有缓存时可离线查询和导出。
- look 工具需要在 Firefox 登录 `https://look.tongji.edu.cn`；视频下载还需要系统可调用 `curl.exe`。

先运行诊断：

```powershell
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" doctor
```

诊断会检查 Python、四个目标脚本、Firefox 配置和 `curl.exe`。它只能确认本地环境，登录态是否过期由实际请求验证。

## 命令

### YourTJ 课程、评价与排课查询

```powershell
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" yourtj search 软件工程
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" yourtj schedule-search 122 --teacher 朱宏明
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" yourtj --help
```

参数完整传给 `选课点评助手\query_yourtj.py`。详细用法见 `..\选课点评助手\README.md`。

### 全校课表导出

```powershell
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule export list-semesters
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule export -c 122 -f csv
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule export -c 122 -f json -o "D:\输出\课表.json"
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule export --help
```

参数完整传给 `同济课表导出\export_schedule.py`。不指定 `-o` 时，结果保存到该工具的 `.cache` 目录。

### 本地课表查询

```powershell
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule query --show-semesters
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule query 大三上 数据库
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule query 122 朱宏明
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" schedule query --help
```

参数完整传给 `同济课表导出\query_schedule.py`。本地 CSV 不存在时，查询脚本会自动调用导出脚本。

### look 录播与课件

```powershell
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" look search 数据库
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" look info 86038
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" look download 86038 2026-05-11
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" look ppt 86038
python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" look --help
```

参数完整传给 `look课程录播\download_look.py`。详细用法和并发扫描限制见 `..\look课程录播\README.md`。

## 调用规则

- 统一入口使用运行自身的 Python 解释器启动目标脚本。
- 每个目标脚本都在自己的目录中运行，缓存和相对路径行为保持不变。
- 标准输入、输出、错误输出及退出码直接保留，便于排错和自动化调用。
- `search-update`、`scan-search` 和课表 `--refresh` 只在明确指定时执行。
