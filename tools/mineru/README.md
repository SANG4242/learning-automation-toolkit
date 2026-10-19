# MinerU：本地解析与云端API

本目录同时收录两条实际使用过的路线，保留完整批处理、缓存与Typora资源整理。

## 本地GPU解析

我的部署是在 WSL2 Ubuntu 24.04 中使用独立 Python 3.12 环境，安装 MinerU 3.2.3、vLLM 0.21.0、PyTorch 2.11.0，模型为 MinerU2.5-Pro-2605-1.2B，GPU 为 RTX 4060 Laptop 8GB。以下命令对应本仓库使用的 **MinerU 3.2.3** 接口；环境与 ASR 的 vLLM 环境分开。

### 1. 安装环境

Windows 的 WSL2 和 NVIDIA 驱动准备参见 [ASR部署说明](../media/README.md#1-准备-windows-和-wsl)。在 Ubuntu 终端中执行：

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv
nvidia-smi
python3.12 -m venv "$HOME/mineru-env"
source "$HOME/mineru-env/bin/activate"
python -m pip install --upgrade pip
python -m pip install 'mineru[vlm,vllm]==3.2.3' 'vllm==0.21.0'
python -m pip check
python -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'
mineru --help
```

`torch.cuda.is_available()` 应为 `True`。包依赖会安装对应的 PyTorch/CUDA 运行时，Windows 驱动需支持它。ASR、对齐与 MinerU 在8GB显卡上分阶段使用，运行解析前先结束其他 GPU 任务。

### 2. 下载并登记模型

在 MinerU 环境中运行官方模型下载器：

```bash
mineru-models-download --source modelscope --model_type vlm
```

下载器会打印模型实际位置，并写入 `~/mineru.json` 的 `models-dir.vlm`。可用以下命令核对本地模型路径：

```bash
python -c 'from pathlib import Path; import json; c=json.loads((Path.home()/"mineru.json").read_text()); p=Path(c["models-dir"]["vlm"]); print(p, p.is_dir())'
```

下载源也可选 `huggingface`。已有本地模型时，在 `mineru.json` 的 `models-dir.vlm` 填写模型目录；自定义配置文件通过 `MINERU_TOOLS_CONFIG_JSON` 的绝对路径指定。包装脚本设置 `MINERU_MODEL_SOURCE=local`，运行时从这份配置读取模型。

### 3. 执行解析

以下以仓库 `D:/study/learning-automation-toolkit` 和共享输出 `D:/study/learning-data` 为例。在 Ubuntu 终端执行：

```bash
cd /mnt/d/study/learning-automation-toolkit
export MINERU_VENV="$HOME/mineru-env"
export MINERU_OUTPUT_DIR=/mnt/d/study/learning-data/mineru-local
bash tools/mineru/local/start_mineru.sh /mnt/d/study/materials/slides.pdf
```

同一条命令可在文件参数后继续添加其他 PDF、图片或 Office 文件。脚本调用 `mineru -b vlm-auto-engine`，按输入路径建立输出子目录，检查已有结果，并将 Markdown 图片路径整理为同名 `.assets/`。

从 Windows 调用时，将 Ubuntu 的用户名和仓库路径替换为自己的值：

```powershell
wsl -d Ubuntu -- env MINERU_VENV=/home/你的Ubuntu用户名/mineru-env MINERU_OUTPUT_DIR=/mnt/d/study/learning-data/mineru-local bash /mnt/d/study/learning-automation-toolkit/tools/mineru/local/start_mineru.sh /mnt/d/study/materials/slides.pdf
```

### 4. 结果、缓存与排错

```text
learning-data/mineru-local/<输入路径编码>/
  slides.md
  slides.assets/
```

已有 Markdown 的子目录会被视为缓存而跳过。源文件更新后，可选择新的 `MINERU_OUTPUT_DIR` 重新解析并保留原结果。默认输出位于仓库 `.local/mineru-local/`。

| 现象 | 检查与处理 |
| --- | --- |
| 虚拟环境或 `mineru` 找不到 | 确认 `MINERU_VENV/bin/activate` 存在，在该环境执行 `mineru --help` |
| 本地模型路径缺失 | 检查 `mineru.json` 的 `models-dir.vlm`，按第二步完成下载和登记 |
| CUDA 不可用 | 对照 `nvidia-smi`、PyTorch CUDA 版本和驱动；先确认 GPU 检测通过 |
| 显存不足 | 结束 ASR 等其他 GPU 任务后再解析，查看 MinerU 日志中的实际错误 |
| 接口或参数不一致 | 查看当前安装版本；本包装使用3.2.3的 `mineru -p/-o/-b` 接口 |

[本地启动脚本](local/start_mineru.sh)和[原环境记录](local/README.md)提供实现及历史参考。上游版本与安装说明见 [MinerU](https://github.com/opendatalab/MinerU)。

## 云端API

- [完整API客户端说明](MinerU%20文档转%20Markdown%20工具说明.md)
- [API参考原文](mineru-api文档.md)

在 [MinerU控制台](https://mineru.net/apiManage/token)取得自己的 API Token，在 PowerShell 中进入仓库并配置客户端：

```powershell
cd 'D:/study/learning-automation-toolkit'
python -m pip install -r requirements.txt
$env:MINERU_API_TOKEN = Read-Host 'MinerU API Token' -MaskInput
python tools/mineru/mineru_pdf2md.py submit 'D:/study/materials/slides.pdf' --output 'D:/study/learning-data/mineru-api'
```

默认提交后轮询并下载结果。任务耗时较长时可分开提交与查询：

```powershell
python tools/mineru/mineru_pdf2md.py submit 'D:/study/materials/slides.pdf' --no-wait
python tools/mineru/mineru_pdf2md.py query 批次ID --output 'D:/study/learning-data/mineru-api'
```

将返回的批次ID填入查询命令。客户端支持混合文件与 URL、页码范围、额外格式和 Markdown／`.assets` 整理。API 路线会上传材料，适用于允许发送到该服务的内容；本地路线在自己的 GPU 环境处理。

PDF页图阅读与结构化解析各有用途：包含图形、公式和版式时可直接保留原页面视觉信息；文字或表格处理按任务选择解析输出。
