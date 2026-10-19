# 语音转录、服务管理、精细对齐与查询

[原项目完整说明](README.original.md)保留三套转录路线、参数、速度记录、切片、VAD、输出、日志与排错细节；[原项目上下文](.agent/原项目入口.md)展示这个工具如何独立维护。

本公开副本保留相关能力，并将模型、解释器、WSL环境和数据目录改成配置，不调用原Hub的脚本或数据。

## 路线选择

| 入口 | 用途 | 输出 |
| --- | --- | --- |
| `transcribe_qwen_vllm.py` | Qwen3-ASR + vLLM，默认5路并发、120–150秒低能量切点、ONNX VAD、重复输出处理 | `transcript.md`、`chunks.json`、`chunks/` |
| `transcribe_qwen.py` | 不启动vLLM的Qwen3-ASR直接模型备用路线 | 分块转录 `transcript.txt` |
| `transcribe.py` | faster-whisper，按时长选择large-v3或turbo，CUDA推理与重复过滤 | 带时间戳 `transcript.txt` |
| `align_qwen.py` | 对ASR分块清单执行字／词级对齐并组织短句索引 | `alignment.jsonl`、`sentences.jsonl` |
| `query_timestamp.py` | 按句子ID、原文或近似字符串查询时间 | 终端显示区间 |
| `bilibili_json_to_txt.py` | 将已有JSON字幕转换为带时间标记的Markdown／文本 | `.md`／`.txt` |

## 部署结构

我在 Windows 运行切片和 HTTP 客户端，在 WSL2 Ubuntu 运行 vLLM，再用单独的 Windows 环境做精细对齐。三者共用音频与任务目录：

```text
Windows 客户端 → HTTP → WSL vLLM / Qwen3-ASR-1.7B
      ↓
transcript.md + chunks.json + chunks/*.wav
      ↓
Windows Qwen3-ForcedAligner-0.6B → alignment.jsonl + sentences.jsonl
      ↓
时间查询 → FFmpeg 抽帧 → AI 选图与写笔记
```

| 部件 | 我的部署版本 | 安装位置示例 |
| --- | --- | --- |
| Windows 客户端 | 本机Python 3.13.7；下文安装示例采用Python 3.12，依赖见 `requirements/asr-client.txt` | `D:/study/envs/asr-client` |
| WSL 推理服务 | Ubuntu 24.04、Python 3.12、vLLM 0.22.0、PyTorch 2.11.0 | `~/vllm-env` |
| Windows 对齐 | Python 3.12、qwen-asr 0.0.6、PyTorch 2.5.1 + CUDA 12.1 | `D:/study/envs/qwen-align` |

以下以仓库 `D:/study/learning-automation-toolkit` 为例。Windows 路径 `D:/study` 在 WSL 中对应 `/mnt/d/study`；模型、音频和结果都放在这块共享目录。硬件参考为 RTX 4060 Laptop 8GB。

## 1. 准备 Windows 和 WSL

Windows 安装支持 WSL CUDA 的 NVIDIA 驱动、Python 3.12 和 FFmpeg；新终端中确认 `ffmpeg -version`、`ffprobe -version` 可运行。WSL2 安装与 GPU 配置见 [Microsoft 指南](https://learn.microsoft.com/windows/ai/directml/gpu-cuda-in-wsl)。尚未安装发行版时，在管理员 PowerShell 执行：

```powershell
wsl --install -d Ubuntu
```

完成系统要求的重启和 Ubuntu 初始化后，在 Ubuntu 终端准备基础包并确认 GPU 可见：

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv ffmpeg curl util-linux
nvidia-smi
```

## 2. 安装 vLLM 服务环境和模型

在 Ubuntu 终端创建独立环境：

```bash
python3.12 -m venv "$HOME/vllm-env"
source "$HOME/vllm-env/bin/activate"
python -m pip install --upgrade pip
python -m pip install 'vllm[audio]==0.22.0' modelscope
python -m pip check
python -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'
modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir /mnt/d/study/models/Qwen3-ASR-1.7B
```

`torch.cuda.is_available()` 应为 `True`。vLLM 的依赖解析负责安装匹配的 PyTorch；驱动需支持该 CUDA 运行时。本机该环境使用 PyTorch 2.11.0 和 CUDA 13。模型下载也可按 [Qwen 官方说明](https://github.com/QwenLM/Qwen3-ASR#released-models-description-and-download)使用 Hugging Face。

## 3. 配置 Windows 客户端

在 PowerShell 中进入仓库，创建客户端环境：

```powershell
cd 'D:/study/learning-automation-toolkit'
py -3.12 -m venv 'D:/study/envs/asr-client'
& 'D:/study/envs/asr-client/Scripts/python.exe' -m pip install -r requirements/asr-client.txt
$env:LEARNING_TOOLS_DATA_DIR = 'D:/study/learning-data'
$env:LEARNING_AUDIO_DIR = 'D:/study/audio'
$env:LEARNING_TRANSCRIPT_DIR = 'D:/study/learning-data/transcripts'
$env:QWEN_WSL_DISTRO = 'Ubuntu'
$env:QWEN_ASR_VENV = '/home/你的Ubuntu用户名/vllm-env'
$env:QWEN_ASR_MODEL = '/mnt/d/study/models/Qwen3-ASR-1.7B'
```

将 `QWEN_ASR_VENV` 替换为第二步环境的绝对 Linux 路径，可在 Ubuntu 中执行 `echo "$HOME/vllm-env"` 查看。`QWEN_ASR_MODEL` 同时用作服务模型路径和请求中的模型名，两个位置保持一致。上面的变量只对当前 PowerShell 会话生效；日常调用可在自己的启动配置中设置。

## 4. 启动和转录

将 `lesson.mp4` 放进 `D:/study/audio`，在配置好的 PowerShell 中执行：

```powershell
& 'D:/study/envs/asr-client/Scripts/python.exe' -u tools/media/transcribe_qwen_vllm.py --file lesson.mp4
Invoke-RestMethod 'http://localhost:8000/v1/models'
```

客户端先检查 localhost，再尝试 WSL 地址；服务未启动时调用本仓库的 `start_vllm_asr.sh` 并等待就绪。转录默认使用5路请求、120–150秒低能量切片与 VAD。任务保存在 `D:/study/learning-data/transcripts/lesson_qwen_vllm/`，包含转录、分块清单及音频。VAD 权重首次使用时自动下载，也可经 `SILERO_VAD_MODEL` 指定已下载文件。

启动器根据可用显存计算预算，记录健康状态、日志与心跳，空闲300秒后释放 GPU。它通过独立进程组管理本次服务。启动日志为 `learning-data/asr-launch.log`，推理日志为 `learning-data/vllm.log`。

需要直接查看启动过程时，在 Ubuntu 中用相同目录手动启动：

```bash
cd /mnt/d/study/learning-automation-toolkit
export QWEN_ASR_VENV="$HOME/vllm-env"
export QWEN_ASR_MODEL=/mnt/d/study/models/Qwen3-ASR-1.7B
export QWEN_ASR_DATA_DIR=/mnt/d/study/learning-data
bash tools/media/start_vllm_asr.sh
```

Linux 原生部署使用同一启动器和客户端，路径均写 Linux 格式；客户端连接服务时使用 `--url http://localhost:8000`。服务默认监听 `127.0.0.1`。WSL NAT 地址直连需要 `QWEN_ASR_HOST=0.0.0.0`，并用防火墙限制访问范围。自定义端口时同时设置 `QWEN_ASR_PORT` 和 `QWEN_ASR_URL`。

## 5. 安装对齐环境

对齐使用独立的 Windows Python 环境，沿用转录清单中的 Windows 音频路径：

```powershell
cd 'D:/study/learning-automation-toolkit'
py -3.12 -m venv 'D:/study/envs/qwen-align'
& 'D:/study/envs/qwen-align/Scripts/python.exe' -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
& 'D:/study/envs/qwen-align/Scripts/python.exe' -m pip install -r requirements/alignment.txt
& 'D:/study/envs/qwen-align/Scripts/python.exe' -m pip check
& 'D:/study/envs/qwen-align/Scripts/python.exe' -c 'import torch; from qwen_asr import Qwen3ForcedAligner; print(torch.cuda.is_available())'
$env:QWEN_ALIGNER_MODEL = 'Qwen/Qwen3-ForcedAligner-0.6B'
```

按模型名加载会下载权重；已有本地权重时，把 `QWEN_ALIGNER_MODEL` 设置为 Windows 模型目录。

## 6. 对齐、定位与抽帧

在第三步配置的同一 PowerShell 会话中使用对齐环境：

```powershell
& 'D:/study/envs/qwen-align/Scripts/python.exe' -u tools/media/align_qwen.py 'D:/study/learning-data/transcripts/lesson_qwen_vllm/chunks.json' --batch-size 4 --stop-vllm
& 'D:/study/envs/asr-client/Scripts/python.exe' tools/media/query_timestamp.py 'D:/study/learning-data/transcripts/lesson_qwen_vllm/sentences.jsonl' S00001
```

8GB显卡分阶段加载 ASR 与对齐模型。`--stop-vllm` 通过共享数据目录向本启动器请求停服；服务已由空闲计时器退出、由其他工具启动或显存足够时，省略这个参数，按实际服务管理方式释放显存。对齐输出与 `chunks.json` 保存在同一任务目录。

查询得到句子区间后，可用 FFmpeg 提取其中一帧。例如定位结果覆盖12分34秒：

```powershell
ffmpeg -ss 00:12:34 -i 'D:/study/audio/lesson.mp4' -frames:v 1 'D:/study/learning-data/frame-12m34.jpg'
```

AI 根据句意选择要看的区间，查看候选画面后按[视频处理流程](../../standards/笔记整理规范/视频图文笔记处理流程.md)保存图片并组织笔记。

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| WSL 启动失败 | 检查 `asr-launch.log`、`QWEN_WSL_DISTRO` 和 `QWEN_ASR_VENV`；在 Ubuntu 中手动执行第四步启动命令查看错误 |
| CUDA 或显存预算错误 | 执行 `nvidia-smi` 和第二步 GPU 检测；结束其他 GPU 任务，可用 `QWEN_GPU_MEMORY_UTILIZATION` 调整预算 |
| 服务就绪但 Windows 无法连接 | 对照 WSL 内 `/health` 与 Windows 的访问结果；按第四步配置监听地址和防火墙 |
| 请求提示模型不存在 | 用 `/v1/models` 核对实际模型标识，并与 Windows `QWEN_ASR_MODEL` 保持一致 |
| 对齐找不到音频 | 核对 `chunks.json` 的 `audio_path`；使用生成转录时的 Windows 路径执行对齐 |
| 对齐停服请求未确认 | 确认客户端和启动器使用同一数据目录，并查看 `vllm.log`；手动停服后运行对齐时省略 `--stop-vllm` |

## 其他两套模型路线

`transcribe_qwen.py`需要Qwen ASR、PyTorch、numpy、soundfile、PyAV及librosa；`transcribe.py`需要faster-whisper和PyAV。安装示例见对应 `requirements/` 文件；运行完整参数沿原说明和 `--help`。

## 配置

| 环境变量 | 含义 |
| --- | --- |
| `LEARNING_TOOLS_DATA_DIR` | 独立数据根，默认仓库 `.local/` |
| `LEARNING_AUDIO_DIR`、`LEARNING_TRANSCRIPT_DIR` | 音视频输入、任务输出 |
| `QWEN_ASR_MODEL`、`QWEN_ALIGNER_MODEL` | 模型名或位置；服务端模型名与客户端请求一致 |
| `QWEN_ASR_URL` | 默认HTTP服务地址 |
| `QWEN_WSL_DISTRO`、`QWEN_ASR_WSL_SCRIPT` | WSL发行版（默认Ubuntu）及可选Linux启动脚本路径 |
| `QWEN_ASR_VENV` | WSL推理虚拟环境（默认`$HOME/vllm-env`） |
| `QWEN_GPU_MEMORY_UTILIZATION` | 显存比例；不设时自动估算 |
| `QWEN_ASR_IDLE_TIMEOUT`、`QWEN_ASR_START_TIMEOUT` | 空闲释放和启动等待秒数，默认300／180 |
| `QWEN_ASR_AUTO_START=0` | 关闭客户端自动启动 |
| `SILERO_VAD_MODEL` | VAD模型位置 |
| `WHISPER_MODEL_DIR` | Whisper权重缓存根 |
| `FFMPEG_BIN_DIR` | FFmpeg目录，可直接使用PATH |

`LEARNING_TOOLS_DATA_DIR`与`QWEN_ASR_DATA_DIR`在Windows客户端和WSL启动器中必须指向同一个物理目录；自动启动会完成对应路径传递。手动启动时按自己的Windows／WSL路径映射配置。

原说明中的解释器和路径为作者环境记录，调用时使用自己安装依赖的 Python 环境。
