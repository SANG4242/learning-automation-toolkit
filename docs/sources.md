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

Course acquisition scripts, original tool manuals, relevant Hub calling guides, full context/note specifications and task plugins are included. Canvas remains a separate service. Original Hub and course directories are not modified by this public copy.

现已收录录播与课程获取脚本、原工具说明、相关Hub调用指南、上下文／笔记规范全文和任务插件；Canvas仍作为独立服务组合使用。这个公开副本不修改原Hub或课程目录。

## Real course material / 真实课程材料

`examples/algorithm-divide-conquer/` contains the full transcript and overview for the 2 April 2026 class, Chapters 3/4/5 slides, complete Chapter 5 notes, all 27 referenced images and the redacted original course context. The author confirms permission to share the teaching materials solely to demonstrate the complete workflow. The original authors/instructor retain their rights; these materials are not granted under the MIT code license. See the case README for attribution and scope.

完整案例保留4月2日转录与概述、Ch3／4／5课件、Ch5笔记及27张图，以及原课程上下文公开副本。课件和课堂内容经许可公开，仅供演示完整整理效果，原作者／授课者保留权利，不按代码MIT许可授权。来源与范围见案例说明。

## Original specifications and manuals / 原规范与说明

The source specifications and manuals retain their structure and detail. Original environment paths and historical examples remain labeled as such; public runnable entry points are mapped in `hub/README.md` and each tool README. Private knowledge links and student/contact information are removed or adapted only in the copies. Plugin examples are newly assembled demonstrations; the historical course's embedded rules remain separately identified.

规范和说明保留原结构与细节。本机路径和历史示例在入口说明，公开执行方式由Hub映射表及工具README给出。私人知识库链接、同学及联系方式仅在副本中脱敏。新的插件化示例与历史课程内嵌规则分开标注，不改写实际形成过程。
