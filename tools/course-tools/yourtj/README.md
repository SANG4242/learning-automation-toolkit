# YourTJ Hub 课程、评价与排课查询工具

调用 `https://f.yourtj.de` 的公开 API，支持课程目录、课程评价、AI 总结和排课器数据查询。公开读取无需登录。

## 运行环境

- Python 3.8 或更高版本，仅使用标准库，无需安装第三方 Python 包。
- 需要能够访问 `https://f.yourtj.de` 的网络；请求失败或接口返回错误时，脚本以非零退出码结束。
- 可通过统一入口调用：`python "D:\Antigravity-Hub\工具脚本\课程工具统一入口\course_tools.py" yourtj <参数>`。

```powershell
cd "D:\Antigravity-Hub\工具脚本\选课点评助手"
python query_yourtj.py --help
python query_yourtj.py <命令> --help
```

## 数据边界

- `courseId`：YourTJ 课程目录主键，只能用于 `/api/forum/*`。
- `offeringId`：YourTJ 课程教学班主键，用于按班筛选评价。
- `calendarId`：一系统学期 ID，也是 `/api/pk/*` 的学期参数，如 `122`。
- `teachingClassId`：一系统教学班 ID，可用于排课与课评精准关联。
- YourTJ 排课高级搜索最多返回 100 门，适合查询和排课；完整全校快照继续使用 `同济课表导出\export_schedule.py` 从一系统抓取。

所有查询命令均支持 `--json` 时，会输出完整原始 JSON，便于脚本处理。

## 课程与评价

### 搜索课程目录

默认只返回有评价课程：

```powershell
python query_yourtj.py search 软件工程
```

包含无评价课程并添加筛选：

```powershell
python query_yourtj.py search 软件工程 --all --teacher 杜庆峰 --term 2026-2027-1 --campus 嘉定校区 --sort rating
```

参数：

```text
--all                 包含无评价课程
--teacher <教师>      可重复
--department <院系>   可重复
--term <学期>         可重复
--campus <校区>       可重复
--sort rating         按评分降序
--json                原始 JSON
```

### 课程详情、教学班与评价

```powershell
python query_yourtj.py info 10503
python query_yourtj.py info 10503 --no-reviews
python query_yourtj.py info 10503 --offering 9394
python query_yourtj.py reviews 10503 --offering 9394
```

`info` 显示课程代码、教师、院系、学分、评分、评价范围、历年教学班、校区和教学班评价统计，并自动游标读取全部评价。

### 相关课程

```powershell
python query_yourtj.py related 10503
```

返回同教师其他课程、同课程其他教师以及课程沿革。

### AI 评价总结

默认只读取已有缓存，不主动生成：

```powershell
python query_yourtj.py summary 10503
python query_yourtj.py summary 10503 --generate
python query_yourtj.py summary 10503 --refresh
```

`--generate` 允许首次生成；`--refresh` 强制重新生成，可能受限流影响。

### 导出评价

```powershell
python query_yourtj.py dump 10503
python query_yourtj.py dump-search 软件工程
python query_yourtj.py dump-search 数据库 -o "D:\输出目录"
```

默认输出：

```text
D:\TJU-Notes\大学课程\选课\大三上\选课点评
```

按已有 `教师_课程.md` 文件名重建目录：

```powershell
python query_yourtj.py refresh-dir "D:\旧点评目录" -o "D:\新版点评目录"
```

只接受课程名与教师同时唯一匹配的课程，不进行猜测覆盖。

## 排课器查询

### 字典与培养计划

```powershell
python query_yourtj.py schedule-calendars
python query_yourtj.py schedule-dictionaries
python query_yourtj.py schedule-grades 122
python query_yourtj.py schedule-majors 2024 --calendar 122
python query_yourtj.py schedule-major-courses 122 2024 42014
```

可查询学期、校区、学院、年级、专业，以及某专业培养计划中的课程和全部教学班。

### 选修课程

```powershell
python query_yourtj.py schedule-optional-types 122
python query_yourtj.py schedule-nature-courses 122 947
```

先查询课程性质 ID，再按一个或多个 ID 获取分组课程。

### 高级搜索与教学班详情

```powershell
python query_yourtj.py schedule-search 122 --name 软件工程
python query_yourtj.py schedule-search 122 --teacher 朱宏明 --campus 嘉定校区
python query_yourtj.py schedule-detail 122 CST3579
python query_yourtj.py schedule-detail 122 CST3579 CST3520
```

`schedule-search` 支持课程名、课程代码、教师姓名、教师工号、校区和学院，最多返回 100 门。`schedule-detail` 返回教学班、`teachingClassId`、教师、教学语言、周次、星期、节次和教室。

### 按时间查课

```powershell
python query_yourtj.py schedule-time 122 4 2
```

`day` 为 1 至 7（周一至周日）；`section` 为排课器的 1 至 6 组，依次对应 1-2、3-4、5-6、7-8、9、10 节。

### 排课与课评联动

```powershell
python query_yourtj.py schedule-review CST3579 --teacher 朱宏明 --calendar 122
python query_yourtj.py schedule-review CST3579 --class-id 1111111124951074 --calendar 122
```

返回对应 YourTJ `courseId`、评分、评价数和课程详情链接；`--class-id` 可按一系统教学班精准匹配。

### 数据状态与节次

```powershell
python query_yourtj.py schedule-latest
python query_yourtj.py schedule-section-times
```

## 官方契约

```text
D:\TJU-Notes\大学课程\选课\YourTJ-Hub\packages\api-contract\openapi.yaml
D:\TJU-Notes\大学课程\选课\YourTJ-Hub\packages\api-contract\paths\courses.yaml
D:\TJU-Notes\大学课程\选课\YourTJ-Hub\packages\api-contract\paths\course-reviews.yaml
D:\TJU-Notes\大学课程\选课\YourTJ-Hub\packages\api-contract\paths\pk.yaml
```
