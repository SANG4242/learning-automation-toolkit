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

Course acquisition and queries (Canvas, recording platforms, course schedules) remain associated projects. This repository concentrates on local material processing and notes. The broader Hub and project-context system remain separate.

课程获取与查询（Canvas、录播平台、课表等）保留为关联项目；本仓库聚焦材料处理和笔记。Hub 与通用项目上下文体系单独维护。
