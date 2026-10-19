# Hub 工具调用导航

[Hub入口示例](.agent/memory.md) · [架构说明](../docs/architecture.md) · [完整规范与插件](../standards/README.md)

Hub 给 AI 一个按任务查找的地图，工具自己的 README 保存详细用法，课程 `.agent` 保存资料和状态。这个目录保留原调用指南全文，下面给出其与公开仓库的对应关系。

## 原文指南

- [文档工具调用](guides/工具-文档.md)
- [音视频工具调用](guides/工具-音视频.md)
- [课程工具调用](guides/工具-课程.md)
- [Hub架构与维护](guides/架构与维护.md)
- [临时文件组织](guides/临时文件.md)

原文中的 `D:\Antigravity-Hub`、`D:\TJU-Notes` 是作者环境角色，不要求读者采用相同盘符。公开执行入口如下，详细参数仍以工具 README 为权威。

| 任务 | 仓库入口 | 详细说明 |
| --- | --- | --- |
| Office转换与PDF页图 | `python tools/documents/doc2img.py 文件.docx`、`python tools/documents/pdf2img.py 课件.pdf` | [文档工具](../tools/documents/README.md) |
| 图片拼接和Markdown图片本地化 | `tools/images/image_stitcher.py`、`localize_md_images.py` | [图片工具](../tools/images/README.md) |
| Qwen/vLLM、直接Qwen、Whisper、对齐与时间查询 | `tools/media/` | [语音与时间工具](../tools/media/README.md) |
| 录播/课件获取、YourTJ、课表 | `python tools/course-tools/course_tools.py --help` | [课程工具](../tools/course-tools/README.md) |
| YouTube/B站媒体与字幕 | 上游 `yt-dlp` CLI | [下载指南](../tools/acquisition/README.md) |
| 本地MinerU结构化解析 | `bash tools/mineru/local/start_mineru.sh 文件.pdf` | [MinerU工具](../tools/mineru/README.md) |
| 云端MinerU批任务 | `python tools/mineru/mineru_pdf2md.py submit 文件.pdf` | [API原说明](../tools/mineru/MinerU%20文档转%20Markdown%20工具说明.md) |
| 课程学习与ASR概述整理 | 上下文规范、项目本地插件与笔记规范 | [完整规范](../standards/README.md) |
| Canvas课程、作业、反馈与资料 | 独立Canvas课程助手CLI/MCP | [关联项目](../tools/acquisition/README.md#canvas课程助手) |

## 调用的顺序

1. 用户提出任务，AI沿Hub入口选择领域或工具。
2. 读取课程／项目入口，确认当前资料与状态。
3. 当前任务匹配插件时读取本地插件；整理笔记同时读取就近完整笔记规范。
4. 使用指南中的命令执行，进一步参数按工具说明或 `--help` 查。
5. 实际查看页面、转录和画面后组织内容，保存来源与图片，再按课程规则写回。

相同信息只由负责它的文件维护。Hub索引不复制各工具的所有参数，也不在每轮对话载入全部课程正文。
