# 学习自动化工具链

[English](README.md) · [项目背景](https://sang4242.pages.dev/zh/projects/course-automation/) · [来源与范围](docs/sources.md)

这是我在学习过程中使用的一组脚本和整理规范：从文档转图开始，逐步加入语音转录、时间对齐、视频选帧，以及带来源和配图的 Markdown 笔记。

工具执行明确的文件操作；AI 助手阅读材料、判断哪里需要放大或看画面、选择图片，再按工作流组织笔记。仓库提供这些工具与约定，整体工作由助手结合材料串联。

## 仓库内容

| 目录 | 内容 |
| --- | --- |
| `tools/documents/` | Word／PPT 转 PDF、PDF 转图、批量输入、Office 引擎感知缓存及拼接调用。 |
| `tools/images/` | 带标签的图片网格；将在线图片归入 Typora 风格 `.assets` 目录。 |
| `tools/media/` | Qwen3-ASR HTTP 客户端、低能量切片、并发、VAD、Forced Aligner 接入、句子时间查询和字幕转换。 |
| `tools/mineru/` | MinerU API 调用、批任务轮询、Markdown 与图片结果整理。 |
| `workflows/` | [课件流程](workflows/slides.md)和[视频流程](workflows/video.md)，供 AI 助手读取执行。 |
| `examples/` | 自制输入、处理步骤和成品笔记。 |
| `tests/` | 无需模型的基础回归。 |

Canvas、课程平台获取和查询等工具保留为关联项目；本仓库集中维护通用材料处理。个人 Hub、真实课程资料与学习进度分别留在原位置。

## 先看示例

![三页自制课件的拼接预览](examples/preview/slides-overview_第1页.jpg)

- [课件笔记](examples/slide-notes.md)：来源页 → 选图 → 解释与页码。
- [视频笔记](examples/video-notes.md)：句子 ID → 时间区间 → 抽帧 → Markdown 图片引用。
- [示例生成脚本](examples/build_demo.py)：创建课件图片、PDF 和 15 秒无声视频，再调用转换、拼接、字幕和抽帧工具。

示例字幕和时间索引由脚本人工定义，用来展示时间查询与画面处理。真实 ASR 和强制对齐需要下面的可选模型环境。

## 安装与轻量流程复现

需要 Python 3.10+，本轮基础检查使用 Windows 11 和 Python 3.13。PDF 转图需要 ImageMagick 7 与 Ghostscript；视频示例需要 FFmpeg。将 `magick`、`ffmpeg`、`ffprobe` 加入 PATH。

```powershell
git clone https://github.com/SANG4242/learning-automation-toolkit.git
cd learning-automation-toolkit
python -m pip install -r requirements.txt
python examples/build_demo.py
python -m unittest discover -s tests -v
```

示例脚本在 `examples/input/` 生成输入，在 `examples/preview/` 保存拼接图，中间页图位于 `.local/`；重跑会更新它自己的演示文件。使用 Typora 或 GitHub 查看笔记与图片。

### 处理自己的文档

```powershell
python tools/documents/pdf2img.py input.pdf --pages 1-3 --output .local/pages
python tools/documents/doc2img.py input.docx --engine office
python tools/documents/ppt2img.py slides.pptx --engine libreoffice --libreoffice-path 'C:/Program Files/LibreOffice/program/soffice.com'
python tools/images/image_stitcher.py -i .local/pages --preset 4
python tools/images/localize_md_images.py notes --dry-run
```

Office 转换调用已安装的 WPS、Microsoft Office 或 LibreOffice；Office／WPS COM 路线仅适用于 Windows。PDF 转图和图片工具可单独使用。默认引擎沿用原工具：`docx2pdf` 默认 WPS，其余 Office 入口默认 Microsoft Office，也可显式指定。

图片本地化去掉 `--dry-run` 后会原地修改 Markdown，运行前检查目标并保留版本。PDF `--force` 会先把旧页图移到 `previous/`，再重新生成。普通页图缓存依据输出文件是否存在；源 PDF 或转换设置变化后，应强制重转。

## 可选：语音转录与精细对齐

模型权重和 GPU 推理环境与基础 Python 依赖分开安装。

1. 使用 `python -m pip install -r requirements/asr-client.txt` 安装客户端依赖。
2. 在 Linux／WSL 准备支持 Qwen3-ASR 的 vLLM 环境。原本机环境使用 vLLM 0.22.0；公开启动样例尚未在干净 GPU 环境重测。`tools/media/start_vllm_asr.sh` 提供参数化前台启动方式，`QWEN_ASR_MODEL` 指定模型位置，显存比例按设备调整。
3. 自行启动服务，再让客户端连接其健康和转录接口。公开客户端只连接指定服务，进程启停由使用者管理。

```powershell
$env:QWEN_ASR_MODEL = 'Qwen/Qwen3-ASR-1.7B'
$env:LEARNING_AUDIO_DIR = 'C:/study/audio'
python tools/media/transcribe_qwen_vllm.py --file lesson.mp4 --url http://localhost:8000 --out-dir .local/transcripts
```

请求中的模型名需与服务提供的名称一致。任务生成 `transcript.md`、`chunks.json` 和分块音频。精细对齐需要匹配 CUDA 的 PyTorch 环境及 `requirements/alignment.txt`：

```powershell
python tools/media/align_qwen.py .local/transcripts/lesson_qwen_vllm/chunks.json --model Qwen/Qwen3-ForcedAligner-0.6B
python tools/media/query_timestamp.py .local/transcripts/lesson_qwen_vllm/sentences.jsonl S00001
```

小显存设备按自己的服务管理方式停止 ASR 后，再加载对齐模型。时间查询支持句子 ID、文本规范化和字符串相似度；AI 助手负责把知识点对应到原文，脚本再给出时间。

### 环境配置

| 变量 | 用途 |
| --- | --- |
| `LEARNING_TOOLS_DATA_DIR` | 中间产物与缓存根目录，默认仓库 `.local/`。 |
| `LEARNING_AUDIO_DIR`／`LEARNING_TRANSCRIPT_DIR` | ASR 输入和输出根目录。 |
| `QWEN_ASR_URL`／`QWEN_ASR_MODEL` | ASR 服务地址及请求模型名。 |
| `QWEN_ALIGNER_MODEL` | 对齐模型名或目录。 |
| `SILERO_VAD_MODEL` | VAD ONNX 位置，缺失时可从上游地址下载。 |
| `FFMPEG_BIN_DIR`／`LIBREOFFICE_PATH` | 可选的外部程序位置。 |
| `MINERU_API_TOKEN` | 云端 MinerU 客户端所需认证。 |

## 可选：结构化解析

```powershell
python tools/mineru/mineru_pdf2md.py --help
python tools/mineru/mineru_pdf2md.py submit document.pdf --output .local/mineru
```

先在环境中设置 `MINERU_API_TOKEN`。该路线会把材料上传到外部 MinerU 服务，仅用于你愿意发送到该服务的内容；本地页图阅读是另一条路线。公开 API 客户端已检查语法和命令入口，真实 API 请求待重测。

## 本轮验证范围

- 实际完成三页 PDF 转图和拼接、人工字幕转换、时间查询、无声视频生成和 FFmpeg 抽帧，并查看了拼接图与选中帧。
- 七项无模型测试覆盖页码、安全命名、时间格式、原文查询、短句拆分、零秒字幕和图片文件名。
- 发布前检查 Python 语法、CLI 入口、Markdown 本地引用和认证信息。
- 公开 ASR／对齐 GPU 环境、Office COM 引擎和云端 MinerU 请求仍需专项端到端验证。示例用于流程复现，转录性能需用实际音频及完整计时条件测量。

## 如何交给 AI 助手使用

提供输入路径、读者基础、笔记位置和适用的 `workflows/` 文件。助手需要脚本执行权限和看图能力，再按内容判断下一步。成品应保留来源、解释配图、区分原材料与补充内容；最后对照原件检查。

## 许可证与上游

自有脚本和自制示例采用 [MIT](LICENSE)。模型、文档引擎与 API 分别遵循自身许可和条款。具体分工见[来源与范围](docs/sources.md)。
