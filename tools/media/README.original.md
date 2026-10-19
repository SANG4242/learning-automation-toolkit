# 语音转录工具集

语音转录目录包含三套转录工具及配套的精细对齐与查询工具，按速度和精度需求选用：

---

## 工具一：faster-whisper（速度优先）

`transcribe.py`，基于 `faster-whisper`，GPU 加速，几分钟内完成转录。支持 `--file` 参数指定单文件转录。

### 使用

音频放进 `temp/语音转录/audio/`，然后运行：

```powershell
python transcribe.py
```

### 参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--model` | `-m` | `large-v3` / `turbo`，不传按时长自动选 |
| `--file` | 无 | 指定单个文件名转录 |
| `--force` | `-f` | 强制重新转录，覆盖已有结果 |
| `--output` | `-o` | 自定义任务名，单文件有效 |
| `--out-dir` | `-d` | 自定义任务目录的父目录 |

### 模型选择逻辑

| 条件 | 模型 |
|------|------|
| 音频 < 20 分钟 | `large-v3`（精度更高） |
| 音频 ≥ 20 分钟 | `large-v3-turbo`（速度约 2× 快） |

### 输出格式

每个音频输出到独立任务目录，转录文件固定为 `transcript.txt`：

```
[006.29s-007.89s] 哈喽大家好，我是彭尼西林
[007.89s-011.79s] 从本期视频开始，我们就来学习 reinforcement learning
```

### 速度

约 4–5× 实时（9 分钟音频约 2 分钟）

---

## 工具二：Qwen3-ASR（精度优先）

`transcribe_qwen.py`，基于 `Qwen3-ASR-1.7B`，精度显著高于 Whisper，尤其适合：
- 中文人名、地名密集场景（Whisper 大量出错）
- 专业术语混合中英文

**代价**：速度约为 Whisper turbo 的 1/10（100 分钟音频约需 30-40 分钟）

### 运行环境

**必须用** conda 环境的 Python，不能用系统 Python：

```powershell
& "D:\Apps\Miniconda3\envs\qwen3-asr\python.exe" "D:\Antigravity-Hub\工具脚本\语音转录\transcribe_qwen.py" [参数]
```

### 参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--file` | `-f` | 指定文件名（如 `数据库测试.wav`），不传则处理 audio 目录全部文件 |
| `--language` | `-l` | 语言（默认 `Chinese`），传 `auto` 自动检测 |
| `--overwrite` | 无 | 强制重跑，忽略已有结果 |
| `--suffix` | `-s` | 任务名后缀（默认 `_qwen`） |
| `--chunk` | `-c` | 每块时长秒数（默认 300，即 5 分钟） |
| `--output` | `-o` | 自定义任务名，单文件有效 |
| `--out-dir` | `-d` | 自定义任务目录的父目录 |

### 示例

```powershell
# 只转一个文件
& "D:\Apps\Miniconda3\envs\qwen3-asr\python.exe" transcribe_qwen.py --file 数据库测试.wav

# 强制重跑
& "D:\Apps\Miniconda3\envs\qwen3-asr\python.exe" transcribe_qwen.py --file p1.m4a --overwrite
```

### 输出格式

每个音频输出到独立任务目录，转录文件固定为 `transcript.txt`。内容为纯文字，每 5 分钟一段，无时间戳：

```
Hello大家好，我是田心念。从本节视频开始，我们就来学习美国训练强化学习...
```

### 支持格式

`.wav`、`.flac`（分块读，低内存）；`.m4a`、`.mp3`、`.mp4`、`.aac`、`.ogg`（PyAV 解码，整体读入）

### 模型路径

```
D:\TJU-Notes\个人项目\asr-models\
├── Qwen3-ASR-1.7B\
└── Qwen3-ForcedAligner-0.6B\    # 备用（时间戳对齐，速度极慢）
```

### Conda 环境

`D:\Apps\Miniconda3\envs\qwen3-asr\`
- Python 3.12，PyTorch 2.5.1 + CUDA 12.1
- 主要包：`qwen-asr`、`soundfile`、`av`（PyAV）

---

## 工具三：Qwen3-ASR + vLLM（精度+速度）⭐ 首选

`transcribe_qwen_vllm.py`，通过 WSL 中的 vLLM 推理服务调用 Qwen3-ASR-1.7B。
兼具 Qwen3 的高精度和 vLLM 的高吞吐。实测 21x 实时（90min 音频 → 4.3min），比 transformers 版快约 7 倍。

### 核心特性

1. **低能量浮动切片 + ONNX CPU VAD（语音活动检测）**
   - 以 150 秒为硬上限，在 120～150 秒范围内优先选择临近上限的低能量切点，减少在说话中间切开；块间无重叠、无缺口。
   - 自动运行 `silero_vad.onnx`；若一个音频块的累计人声不足 2 秒，则跳过 ASR 请求并保留无声占位。
2. **任务目录、时间范围与熔断去重**
   - 每个音频使用独立任务目录，集中保存 `transcript.md`、`chunks.json`、`chunks/` 和后续对齐结果。
   - Markdown 为每块标注真实时间范围，如 `[02:27-04:50]`；精确到秒，不足一小时省略小时位。
   - 自动检测并截断连续重复的幻觉文本。
3. **代理自动直连**
   - 自动在 Python 脚本对 vLLM 接口屏蔽 Windows 系统代理软件（如 Clash/V2Ray 代理），防止因局域网转发拦截造成 ConnectionError，运行转录时无需手动关闭系统代理。

### 跨窗口批次等待

运行 `transcribe_qwen_vllm.py` 时，所有窗口共用 `temp/语音转录/.vllm_transcription.lock` 的操作系统文件锁。后启动的窗口显示等待提示，获得锁后才检查或启动服务，并处理本批全部音频；批次内部仍默认 5 路并发。

正常完成、报错或进程退出后锁会释放；等待时可按 Ctrl+C 取消。锁文件会保留，无需手动删除。多个等待窗口不保证严格按启动顺序接续。修改前已启动的旧进程不受新锁保护，首次使用应等旧任务完成。此锁仅协调本脚本，不协调其他转录工具或精细对齐脚本。

### 服务管理与一键自启动（新功能） ⭐

本脚本已实现 **客户端全自动托管**，您**无需手动前置启动 vLLM 服务**：
1. **自动拉起**：运行转录脚本时，若检测到 vLLM 后端服务未运行，客户端会自动在后台拉起 WSL 端的启动脚本（`start_vllm_asr.sh`）并自动轮询等待服务就绪，完全无需人工干预。
2. **故障重路由**：若遇到代理软件等导致的 Windows `localhost:8000` 本地转发失效（即服务实际在运行却连接超时），客户端会自动获取 WSL2 虚拟机的真实 IP 直连（如 `172.19.xx.xx`），实现 **网络直连重路由**，强行穿透代理拦截。

**服务特性：**
- **自动显存分配**：启动时通过 CUDA 检测可用显存，自动计算最优 `gpu-memory-utilization`
- **5 分钟空闲自动关闭**：无转录请求时看门狗自动释放显存，彻底归还 GPU 资源
- **手动后台拉起备用命令**：若想手动前置启动，可执行：
  ```powershell
  wsl -d Ubuntu -- bash /mnt/d/Antigravity-Hub/工具脚本/语音转录/start_vllm_asr.sh
  ```
- **手动强行关闭命令**：
  ```powershell
  wsl -d Ubuntu -- pkill -f "vllm serve"
  ```

### 使用（系统 Python 即可）

```powershell
python "D:\Antigravity-Hub\工具脚本\语音转录\transcribe_qwen_vllm.py" [参数]
```

### 参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--file` | `-f` | 指定文件名（支持以英文逗号分隔指定多个文件进行排队转录），不传则处理全部 |
| `--language` | `-l` | 识别语言（默认 `zh`。英文传 `en`） |
| `--overwrite` | 无 | 强制重跑 |
| `--suffix` | `-s` | 输出后缀（默认 `_qwen_vllm`） |
| `--chunk` | `-c` | 每块硬上限秒数（默认且最大 150） |
| `--min-chunk` | 无 | 开始寻找低能量切点的位置（默认 120） |
| `--workers` | `-w` | 并发数（默认 5；RTX 4060 Laptop 8GB 长视频实测最优） |
| `--output` | `-o` | 自定义任务名，单文件有效 |
| `--out-dir` | `-d` | 自定义任务目录的父目录（默认全局 `output/`） |
| `--url` | 无 | vLLM 服务地址（默认 `http://localhost:8000`） |

### 示例

```powershell
# 只转录一个中文音频文件
python transcribe_qwen_vllm.py -f 数据库测试.wav

# 转录多个音频文件（以英文逗号分隔，自动排队连续转录）
python transcribe_qwen_vllm.py -f "计算机系统结构_2026-03-12.mp4,计算机系统结构_2026-03-19.mp4"

# 指定任务目录的父目录
python transcribe_qwen_vllm.py -f 数据库测试.wav -d "D:\Antigravity-Hub\temp\语音转录\output"

# 转录英文音频文件（指定语言为 en 且强制覆写）
python transcribe_qwen_vllm.py -f xAI_Colossus.webm -l en --overwrite
```

### Forced Aligner 精细时间戳

转录后，任务目录包含 `transcript.md`、`chunks.json` 和 `chunks/`。使用 conda 环境运行对齐；脚本默认通过模型原生 batch 一次处理 4 个组块。8GB 显存机器应加 `--stop-vllm`：

```powershell
& "D:\Apps\Miniconda3\envs\qwen3-asr\python.exe" "D:\Antigravity-Hub\工具脚本\语音转录\align_qwen.py" "D:\Antigravity-Hub\temp\语音转录\output\任务名\chunks.json" --stop-vllm
```

可用 `--batch-size` 调整每批组块数；默认值为 4：

```powershell
& "D:\Apps\Miniconda3\envs\qwen3-asr\python.exe" "D:\Antigravity-Hub\工具脚本\语音转录\align_qwen.py" "任务目录\chunks.json" --batch-size 4 --stop-vllm
```

原生 batch 与 ASR 的 `--workers` 不同：前者将多组音频和参考文本组成一次模型前向计算，后者同时向 vLLM 提交多个独立请求，由服务端动态调度。

本机 RTX 4060 Laptop 8GB 实测：4 个 119～150 秒组块共 560 秒，batch 4 对齐计算约 5.5～6.0 秒，峰值分配显存约 4.13 GiB。与串行结果相比，2551 个字/词级对齐单元及 80 个短句的文本和顺序完全一致，平均时间戳绝对差约 0.0006 秒，单个边界最大差 0.64 秒。

输出：

- `alignment.jsonl`：完整字/词级时间戳，作为底层数据。
- `sentences.jsonl`：不超过 100 字的短句索引，供查询与截图定位。

按句子 ID 或原文片段查询；查询器会流式扫描索引，并支持相邻 2～3 句组合匹配：

```powershell
python "D:\Antigravity-Hub\工具脚本\语音转录\query_timestamp.py" "D:\Antigravity-Hub\temp\语音转录\output\任务名\sentences.jsonl" "需要定位的原文"
python "D:\Antigravity-Hub\工具脚本\语音转录\query_timestamp.py" "D:\Antigravity-Hub\temp\语音转录\output\任务名\sentences.jsonl" "S00001"
```

### 依赖

- Windows 侧：`requests`（pip install requests）、`ffmpeg`（需在 PATH 中）
- WSL 侧：`~/vllm-env/` 虚拟环境（vLLM 0.22.0 + PyTorch 2.11 + CUDA 13）

### 启动脚本配置说明（start_vllm_asr.sh）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `gpu-memory-utilization` | auto（~0.85） | 通过 `torch.cuda.mem_get_info()` 自动检测 |
| `max-model-len` | 4096 | 单次请求最大 token 序列长度（降低以缓解 8GB 显卡下的 Profiling 阶段显存开销） |
| `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS` | 0 | 禁用 CUDA graph 内存预估（v0.21+ 默认开启会额外预留约 10%，8GB 显卡上会导致 KV cache 不足） |
| `VLLM_DISABLE_FLASHINFER` | 1 | CUDA 13 与 FlashInfer JIT 不兼容 |
| 空闲超时 | 300s（5 分钟） | 心跳文件 `.vllm_heartbeat` 超时后自动关闭 |

### WSL 环境信息

| 项 | 内容 |
|---|---|
| WSL 发行版 | Ubuntu (Noble 24.04) |
| venv 路径 | `~/vllm-env/` (11GB) |
| 代理 | 自动通过 `~/.wsl_proxy.sh` 获取 Windows Clash 代理 |
| sudo | 免密（已配置 `/etc/sudoers.d/sang`） |
| apt 源 | 清华镜像 |
| VRAM 占用 | ~7.7 GiB（运行时峰值） |

---

## 文件目录

```
Hub\工具脚本\语音转录\
├── transcribe.py              # Whisper 脚本
├── transcribe_qwen.py         # Qwen3-ASR 脚本（transformers 直推）
├── transcribe_qwen_vllm.py    # Qwen3-ASR 脚本（vLLM API 版）
├── align_qwen.py              # Forced Aligner 分块对齐与短句索引
├── query_timestamp.py         # 按短句 ID 或原文查询时间戳
└── start_vllm_asr.sh          # vLLM 服务启动脚本（WSL 中运行）

Hub\temp\语音转录\
├── audio\                     # 待转录音视频
└── output\
    ├── 任务名\                 # 一次 ASR 任务的全部产物
    │   ├── transcript.md       # vLLM 版正式转录；备用脚本为 transcript.txt
    │   ├── chunks.json         # vLLM 分块清单
    │   ├── chunks\             # vLLM 分块 WAV
    │   ├── alignment.jsonl     # 精细字/词时间戳（按需）
    │   └── sentences.jsonl     # 短句索引（按需）
    └── 平台字幕等对照材料

TJU-Notes\个人项目\asr-models\     # 模型权重（D 盘）
```

---

## 对比总结

| | Whisper turbo | Whisper v3 | Qwen3-ASR (transformers) | Qwen3-ASR (vLLM) |
|---|---|---|---|---|
| 速度（90min 音频） | ~172s（31x 实时） | - | ~30-40 分钟 | ~258s（21x 实时） |
| 中文专业术语 | 一般 | 较差 | 优秀 | 优秀 |
| 中文人名识别 | 差 | 差 | 优秀 | 优秀 |
| 时间戳 | 句级，精确 | 句级，精确 | 无 | 无 |
| VRAM 占用 | ~2 GB | ~4 GB | ~4.6 GB | ~7.7 GB（5min 空闲自动释放） |
| 环境要求 | 系统 Python | 系统 Python | conda 环境 | WSL + vLLM 服务 |
| 推荐场景 | 需要时间戳时 | 不推荐 | 无 WSL 时备用 | **首选**（精度+速度） |
