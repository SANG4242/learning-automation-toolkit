# Sources and scope / 来源与范围

The Python scripts are extracted from tools used in my local study workflow. This public version separates machine configuration and private course material from reusable code. Development used AI assistance, followed by local use, debugging and incremental changes.

Python 脚本来自个人学习过程中维护的本地工具。公开版把机器配置、认证和真实课程资料分离，保留可复用实现。开发使用 AI 协助，并通过本地使用、调试和迭代调整。

| Component / 组件 | This repository / 本仓库工作 | Upstream / 上游 |
| --- | --- | --- |
| Office/PDF | Engine selection, cache, batch wrappers, rendering and stitching integration / 引擎选择、缓存、批处理、转图与拼接编排 | WPS, Microsoft Office, LibreOffice, ImageMagick, Ghostscript |
| Images | Grid layout and labels, Markdown image localization / 网格布局、标签及 Markdown 图片本地化 | Pillow; Python standard library |
| ASR | Low-energy chunk boundaries, concurrency, VAD filtering, task manifests / 低能量切片、并发、语音过滤与任务清单 | [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR), [vLLM](https://github.com/vllm-project/vllm), [Silero VAD](https://github.com/snakers4/silero-vad), FFmpeg |
| Alignment | Chunk offsets, sentence indices and text lookup / 分块偏移、短句索引和原文查询 | Qwen3-ForcedAligner and PyTorch |
| Parsing | API requests, batch polling and Markdown/assets output organization / API 调用、批任务查询与输出整理 | [MinerU](https://github.com/opendatalab/MinerU) and its API |
| Workflow | Source anchors, visual selection and note structure / 来源锚点、选图和成文要求 | AI host/model supplied by the user / 使用者提供AI宿主及模型 |

The MIT license covers the repository's own scripts and authored examples. External software, model weights, APIs and documents retain their own licenses and terms. Model weights and external executable distributions are not included.

MIT 适用于本仓库自有脚本与自制示例。外部软件、模型权重、API 和文档分别遵循自身许可与使用条件；仓库不包含模型权重或外部软件发行包。

The repository includes course acquisition scripts, tool manuals, Hub calling guides, context and note specifications, and task plugins. Canvas integrates as a separate service.

仓库收录录播与课程获取脚本、工具说明、Hub调用指南、上下文与笔记规范及任务插件；Canvas作为独立服务组合使用。

## Real course material / 真实课程材料

`examples/algorithm-divide-conquer/` contains the transcript and overview for the 2 April 2026 class, Chapters 3/4/5 slides, Chapter 5 notes, 27 image assets (25 referenced in the notes) and the course context. The teaching materials are shared with permission solely to demonstrate the workflow. Their original authors/instructor retain their rights; see the case README for attribution and terms.

完整案例保留4月2日转录与概述、Ch3／4／5课件、Ch5笔记及27张图，以及原课程上下文公开副本。课件和课堂内容经许可公开，仅供演示完整整理效果，原作者／授课者保留权利，不按代码MIT许可授权。来源与范围见案例说明。

## Original specifications and manuals / 原规范与说明

The specifications and manuals retain their structure and detail. The Hub command map and tool READMEs explain how to use the example paths in this repository. Private links and personal identifiers are adapted in the public material. The course case includes its original context; the plugin example shows installation and course-specific configuration.

规范和说明保留原结构与细节。本机路径和示例的对应关系由Hub映射表及工具README说明。私人链接和身份信息已在公开副本中处理；课程案例保留当时的上下文，插件示例提供安装与特化配置。
