# 学习自动化工具链

[English](README.md) · [项目介绍](https://sang4242.pages.dev/zh/projects/course-automation/) · [上下文系统](https://sang4242.pages.dev/zh/projects/agent-context/)

这是我在整个大二学年的课程学习中使用和持续调整的一套工具与规范。从课件转图、拼接预览开始，逐步加入录播获取、语音转录、课堂概述、时间对齐、按需抽帧和图文笔记。经过一学期的持续使用与调整，各个部件在我的本机环境中已基本稳定。

**Hub 统筹导航、任务分流和共享工具入口；各层 `.agent` 管理本层资料与状态，AI 沿索引逐层下钻。笔记整理规范规定工具调用、阅读与成文步骤，AI 据此执行并判断下一步。**

## 先看完整真实案例

[算法设计与分析：2026-04-02 分治法课](examples/algorithm-divide-conquer/README.md)保留整条实际资料链：

| 资料 | 直接阅读 |
| --- | --- |
| 完整ASR原文 | [当天课堂转录](examples/algorithm-divide-conquer/ASR转录/算法设计与分析_2026-04-02_qwen_vllm.md) |
| 课堂概述与课件映射 | [当天概述](examples/algorithm-divide-conquer/.agent/asr概述/2026-04-02_Ch5.md) |
| 完整课件 | [Ch5分治法及Ch3／Ch4复习课件](examples/algorithm-divide-conquer/课件/) |
| 章节笔记与27张图片资源 | [完整分治法笔记](examples/algorithm-divide-conquer/笔记/ch5_分治法.md) |
| 课程上下文 | [案例资料入口](examples/algorithm-divide-conquer/.agent/memory.md)、[原课程规则](examples/algorithm-divide-conquer/.agent/context/原课程上下文.md) |

![实际章节笔记使用的课件P7](examples/algorithm-divide-conquer/笔记/ch5_分治法.assets/ch5_P7.jpg)

课程课件和课堂转录经许可公开，**仅用于演示完整整理效果**，原作者／授课者保留权利，来源与使用范围见案例说明。

## 整体架构

```text
Hub .agent：全局导航、任务分流、共享工具入口
  ├─ 领域.agent → 子领域.agent → 课程或项目.agent
  │    └─ 本层资料、状态、规则与下一层入口
  └─ 工具指南 → 工具README／.agent → 脚本／模型／外部程序

课程.agent → 任务插件与笔记规范 → 按步骤调用工具、阅读和选图
                               → 概述／笔记／图片及学习记录
```

- **逐层读取**：先建立内容分布印象，再进入当前任务相关资料；详细参数和课程细节下放到各自入口。
- **三文件分工**：稳定信息、当前状态、完成历史各有位置，新窗口能沿记录继续。
- **插件化**：课程讲解、ASR录播整理等任务流程可以独立安装，按触发时机加载；课程特化放在本地插件开头，升级时保留。
- **AI与工具配合**：脚本执行转换、下载、转录和抽帧；AI判断看不看得清、哪些画面有用、如何核对和组织内容。

详细设计见[架构与使用](docs/architecture.md)，实际导航见[Hub入口](hub/.agent/memory.md)，插件如何落地见[插件课程示例](examples/plugin-course/README.md)。

## 完整规范与插件

规范目录提供上下文、任务插件和笔记整理的正文、模板与版本记录。

| 规范 | 用途 |
| --- | --- |
| [上下文规范库与插件总索引](standards/上下文规范/.agent/memory.md) | 类型选择、安装、版本与升级 |
| [通用项目规范](standards/上下文规范/通用项目/通用项目上下文规范.md) | 软件、工具和交付项目的上下文 |
| [课程学习规范](standards/上下文规范/课程学习/课程学习上下文规范.md) | 理论课程、章节学习和答疑 |
| [课程任务规范](standards/上下文规范/课程任务/课程任务上下文规范.md) | 报告、展示、作业类课程 |
| [课程讲解与答疑插件](standards/上下文规范/课程学习/插件/课程讲解与答疑.md) | 资料选择、节奏与讲解方式 |
| [ASR录播整理插件](standards/上下文规范/课程学习/插件/ASR录播整理.md) | 转录查阅、概述、课堂重点和课件映射 |
| [PPT课件笔记规范](standards/笔记整理规范/PPT课件笔记整理规范.md) | 前置知识、解释、逐页来源与图片 |
| [视频图文笔记规范](standards/笔记整理规范/视频图文笔记整理规范.md) | 讲解主线、时间锚点、配图与成文 |
| [视频处理流程](standards/笔记整理规范/视频图文笔记处理流程.md) | 获取、转录、对齐、抽帧和选图 |

可以为特定任务继续增加插件：把适用前提、读取时机、输入、流程、输出与写回位置写清楚，复制到项目 `.agent/plugins/` 并在入口登记即可。规范源更新不自动覆盖项目；个人配置与通用正文分开维护。完整说明见[规范入口](standards/README.md)。

## 工具与原说明

| 模块 | 已收录能力 | 入口与详细原文 |
| --- | --- | --- |
| 材料获取 | Look录播／课件、断点续传、长度检查、重试；yt-dlp视频及字幕调用 | [获取指南](tools/acquisition/README.md) |
| 课程工具 | 统一入口、YourTJ、课表导出／查询、Look工具 | [完整工具与README](tools/course-tools/README.md) |
| 文档处理 | Word/PPT→PDF→页图，WPS／Office／LibreOffice，批处理、缓存、页码与拼接 | [详细说明](tools/documents/README.md) |
| 图片处理 | 网格预览、选图、标签、ImageMagick命令、Markdown图片本地化 | [详细说明](tools/images/README.md) |
| ASR与时间 | vLLM并发、低能量切片、VAD、自动WSL启动与空闲释放、直接Qwen和Whisper备用、对齐与查询 | [完整说明及原项目.agent](tools/media/README.md) |
| MinerU | 本地GPU包装、API批任务、轮询、缓存、Markdown与.assets整理 | [两条路线及原说明](tools/mineru/README.md) |

Hub的[文档](hub/guides/工具-文档.md)、[音视频](hub/guides/工具-音视频.md)、[课程](hub/guides/工具-课程.md)原调用指南也已保留。[公开命令导航](hub/README.md)说明本机原路径与仓库入口的对应关系。Canvas课程助手继续作为独立项目通过CLI／MCP组合使用。

## 开始使用

先克隆仓库，选择自己需要的模块。基础图片处理需要Python 3.10+和Pillow；文档转图需要ImageMagick与Ghostscript；媒体处理需要FFmpeg。Office转换和GPU推理环境分别按对应工具README安装。

```powershell
git clone https://github.com/SANG4242/learning-automation-toolkit.git
cd learning-automation-toolkit
python -m pip install -r requirements.txt
python tools/documents/pdf2img.py 课件.pdf --output .local/pages
```

为自己的课程建立上下文，安装所需插件，并给AI提供课程入口、原件位置与目标。比如：“按课程入口和已安装插件，先整理这一讲的ASR概述，再按完整课件规范制作笔记。”AI沿索引选资料、调用工具、查看结果，再写回课程文件。

ASR主入口示例：

```powershell
python -m pip install -r requirements/asr-client.txt
$env:LEARNING_AUDIO_DIR = 'C:/study/audio'
$env:QWEN_ASR_MODEL = 'Qwen/Qwen3-ASR-1.7B'
python -u tools/media/transcribe_qwen_vllm.py --file lesson.mp4
```

部署按需要选择：

- [ASR部署](tools/media/README.md#部署结构)：Windows客户端、WSL vLLM、模型下载、共享路径、自动启动、对齐与排错。
- [MinerU部署](tools/mineru/README.md#本地gpu解析)：独立WSL环境、模型配置、本地批处理，以及云端API提交与查询。

中间数据默认保存在仓库 `.local/`，由 `LEARNING_TOOLS_DATA_DIR` 配置。安装后将工具入口登记到自己的 Hub，课程中的笔记规范即可按任务使用。

## 使用情况与反馈

这套工具源于我自己的长期学习实践，目前主要在我的本机环境使用。GitHub版本抽离了个人路径、配置与认证，与本地日常版本存在差异。如果你在实际运行中遇到问题，欢迎[提交Issue](https://github.com/SANG4242/learning-automation-toolkit/issues)，我会尽力协助排查和解决。

[小型自制演示](examples/slide-notes.md)和[视频定位演示](examples/video-notes.md)便于快速尝试页图、时间查询和抽帧。

## 许可与来源

自有脚本、规范和自制演示采用[MIT](LICENSE)。真实课程案例中的课件与课堂内容仅按案例说明用于效果展示；模型、引擎、API和第三方文档遵循自身许可。具体来源见[组件与原稿说明](docs/sources.md)。
