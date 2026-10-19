# 图片网格、处理与 Markdown 资源

## 图片拼接

[完整原说明](docs/image_stitcher使用说明.md)包括布局、序号选择、文件匹配、标签、主题及尺寸参数。

```powershell
python tools/images/image_stitcher.py -i .local/pages/lesson --preset 4 --auto-size
python tools/images/image_stitcher.py -i .local/pages/lesson --select 1,3-5
```

拼接图用于快速了解结构，看不清的公式、文字或图表仍读取单页。宿主显示和压缩方式不同，查看成图后决定分辨率。

## Markdown 图片本地化

[完整原说明](docs/使用说明.md)包括 Markdown/HTML 图片、`.assets` 目录和原地替换方式。

```powershell
python tools/images/localize_md_images.py 笔记目录 --dry-run
python tools/images/localize_md_images.py 笔记目录
```

去掉 `--dry-run` 后下载图片并更新 Markdown；处理自己的笔记副本或已纳入版本管理的文件。

## 通用图片命令

[ImageMagick通用命令指南](docs/ImageMagick通用命令指南.md)保留裁剪、切割、缩放、格式转换等调用方法。原说明里的本机脚本路径替换为本目录入口即可。
