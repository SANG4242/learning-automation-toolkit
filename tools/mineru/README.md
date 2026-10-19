# MinerU：本地解析与云端API

本目录同时收录两条实际使用过的路线，保留完整批处理、缓存与Typora资源整理。

## 本地GPU解析

- [原环境与使用说明](local/README.md)
- [完整启动包装](local/start_mineru.sh)

```bash
export MINERU_VENV="$HOME/mineru-env"
export MINERU_OUTPUT_DIR="$PWD/.local/mineru-local"
bash tools/mineru/local/start_mineru.sh /path/to/课件.pdf /path/to/讲义.docx
```

保留VLM后端、批量输入、确定性路径编码、已有结果缓存、Markdown及同名`.assets`输出。虚拟环境需安装MinerU及对应GPU依赖和模型，版本与原环境记录见原说明；`MINERU_VENV`、`MINERU_OUTPUT_DIR`替换个人固定路径。

## 云端API

- [完整API客户端说明](MinerU%20文档转%20Markdown%20工具说明.md)
- [API参考原文](mineru-api文档.md)

```powershell
python tools/mineru/mineru_pdf2md.py --help
python tools/mineru/mineru_pdf2md.py submit 课件.pdf --output .local/mineru
```

认证通过 `MINERU_API_TOKEN` 环境变量提供。保留异步批任务、结果查询、轮询和资源整理；这条路线会把材料发送到MinerU服务，本地路线则在自己的环境处理。

PDF页图阅读与结构化解析各有用途：包含图形、公式和版式时可直接保留原页面视觉信息；文字或表格处理按任务选择解析输出。
