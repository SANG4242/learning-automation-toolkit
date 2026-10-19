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

## vLLM主路线

Windows客户端安装 `requirements/asr-client.txt`。在Linux或WSL安装支持Qwen3-ASR的vLLM和匹配CUDA的PyTorch，准备模型，配置虚拟环境。原使用环境的版本与实测记录见原说明。

```powershell
$env:LEARNING_AUDIO_DIR = 'C:/study/audio'
$env:QWEN_ASR_MODEL = 'Qwen/Qwen3-ASR-1.7B'
python -u tools/media/transcribe_qwen_vllm.py --file lesson.mp4 --out-dir .local/transcripts
```

默认先检查localhost服务，Windows映射异常时尝试WSL地址；未运行时自动启动本目录的 `start_vllm_asr.sh` 并等待就绪。Linux直接启动脚本，外部服务使用 `--url`。

启动器保留自动显存预算、启动健康检查、日志、心跳和空闲5分钟释放。服务状态、PID和日志位于独立 `.local/`，只管理它自己启动的进程组。请求期间更新心跳；`--stop-vllm`可在加载对齐模型前发出停止请求。

```bash
export QWEN_ASR_MODEL=Qwen/Qwen3-ASR-1.7B
export QWEN_ASR_VENV="$HOME/vllm-env"
bash tools/media/start_vllm_asr.sh
```

默认监听本机。若WSL需要IP回退，可设置 `QWEN_ASR_HOST=0.0.0.0` 并通过系统防火墙限定访问；不需要时保持localhost即可。

## 对齐与定位

在有CUDA的推理环境安装 `requirements/alignment.txt` 和匹配的PyTorch：

```powershell
python -u tools/media/align_qwen.py .local/transcripts/lesson_qwen_vllm/chunks.json --stop-vllm
python tools/media/query_timestamp.py .local/transcripts/lesson_qwen_vllm/sentences.jsonl S00001
```

显存足够或服务由其他方式管理时不传 `--stop-vllm`。查询支持ID和原文匹配；助手先理解知识点并找到相关原句，再用时间结果抽帧。

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

原说明中固定解释器和个人路径是当时环境示例，公开命令使用自己安装依赖的Python环境。工具原有`.agent`的私人进度和历史不随公开副本分发，稳定架构入口保留。
