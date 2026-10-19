# 文档转换与 PDF 页图

本目录保留原工具的完整实现：Office 转 PDF、引擎选择、缓存、批处理、PDF 页码选择、自动分辨率、转图及拼接调用。

## 完整说明

- [Office转换原说明](docs/Word文档转换工具说明.md)：四个入口、引擎、批量、缓存与排错。
- [PDF转图片原说明](docs/PDF转图片工具说明.md)：分辨率、页码、格式、缓存与拼接。

原说明保留详细内容与个人环境示例；在公开仓库执行时，用以下入口替换原 Hub 路径：

```powershell
python tools/documents/docx2pdf.py 文件.docx --engine wps
python tools/documents/ppt2pdf.py 课件.pptx --engine office
python tools/documents/doc2img.py 文件.docx --engine office
python tools/documents/ppt2img.py 课件.pptx --engine libreoffice
python tools/documents/pdf2img.py 课件.pdf --pages 1-5 --output .local/pages --names lesson
```

输出根目录由 `LEARNING_TOOLS_DATA_DIR` 配置，默认 `.local/`。Word PDF 在 `word-pdf/`、PPT PDF 在 `slides-pdf/`，页图在 `pdf-images/`；指定 `--output` 可覆盖。LibreOffice可经PATH、`LIBREOFFICE_PATH`或`--libreoffice-path`定位。

依赖为 Python、相应 Office/WPS/LibreOffice；PDF 渲染需要 ImageMagick 和 Ghostscript，拼接需要 Pillow。Office/WPS COM 路线适用于 Windows。`docx2pdf` 默认 WPS，其余 Office 入口默认 Microsoft Office。

PDF 缓存依据已有输出文件；源文件或参数改变后使用 `--force`，旧页图会移动到 `previous/`。渲染后两页以上默认拼接，可用 `--no-stitch` 关闭。原说明中的旧默认行为若与这里不同，以公开入口和 `--help` 为准。
