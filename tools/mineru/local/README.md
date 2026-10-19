# MinerU 本地文档解析

基于 MinerU 3.2.3 + VLM 后端（MinerU2.5-Pro-1.2B），在 WSL 中通过 vLLM 本地运行。效果与官方在线版一致。

## 环境

| 项 | 值 |
|---|---|
| venv | `~/mineru-env/`（WSL，~8.7GB） |
| 模型 | `~/.cache/modelscope/.../MinerU2.5-Pro-2605-1.2B`（WSL，~2.15GB） |
| 后端 | vlm-auto-engine（GPU 加速，RTX 4060 8GB） |

## 使用

```bash
# 单文件
wsl -d Ubuntu -- bash /mnt/d/TJU-Notes/个人项目/MinerU文档解析/start_mineru.sh "/mnt/d/路径/文件.pdf"

# 多文件
wsl -d Ubuntu -- bash /mnt/d/TJU-Notes/个人项目/MinerU文档解析/start_mineru.sh "/mnt/d/a.pdf" "/mnt/d/b.docx"
```

## 输出

位置：`D:\Antigravity-Hub\temp\MinerU转换\<路径编码>\`

```
MinerU转换/
  TJU-Notes_大学课程_xxx_文件名/
    文件名.md
    文件名.assets/
      image1.jpg
      image2.jpg
```

已转换文件自动跳过（缓存检查）。

## 与官方 API 的区别

| | 本地（本脚本） | 官方 API（mineru_pdf2md.py） |
|---|---|---|
| 速度 | 即时（GPU 加速） | 需排队（高峰期 500+ 人） |
| 网络 | 不需要 | 需要上传文件到云端 |
| 文件限制 | 无 | 200MB |
| 支持格式 | PDF/图片/DOCX/PPTX/XLSX | 同左 + URL/HTML |
