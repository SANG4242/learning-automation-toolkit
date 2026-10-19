# ImageMagick 通用命令指南

> 本文档汇总 ImageMagick 的常用命令，涵盖图片处理的各种场景。

[TOC]

## 安装信息

- **版本**：ImageMagick 7.1.2-Q16-HDRI
- **安装路径**：`C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\`
- **安装方式**：Chocolatey (`choco install imagemagick`)
- **安装日期**：2026-01-11

> ⚠️ 如果 `magick` 命令无法识别，需要重启终端或使用完整路径：
> ```powershell
> & "C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe" ...
> ```

---

## 📐 图片裁剪 (Crop)

### 按像素裁剪

```powershell
# 从左上角 (0,0) 裁剪 800x600 的区域
magick input.png -crop 800x600+0+0 output.png

# 从位置 (100,50) 开始裁剪 800x600
magick input.png -crop 800x600+100+50 output.png
```

### 按百分比裁剪

```powershell
# 裁剪中间 50% 的区域
magick input.png -gravity center -crop 50%x50%+0+0 output.png
```

### 去除边缘空白 (Trim)

```powershell
# 自动去除图片边缘的空白区域
magick input.png -trim +repage output.png
```

---

## ✂️ 图片切割 (Split)

### 按网格切割

```powershell
# 切成 2x2 网格 (4张图)
magick input.png -crop 2x2@ +repage +adjoin output_%d.png

# 切成 3x3 网格 (9张图)
magick input.png -crop 3x3@ +repage +adjoin output_%d.png

# 切成 1x10 网格 (垂直切成10张，适合长截图)
magick input.png -crop 1x10@ +repage +adjoin output_%d.png
```

### 按固定尺寸切割

```powershell
# 每 1080x1920 切一块 (适合手机截图宽度)
magick input.png -crop 1080x1920 +repage +adjoin output_%d.png

# 每 1920 像素高度切一块 (垂直切割长截图)
magick input.png -crop x1920 +repage +adjoin output_%d.png
```

### 微信长截图切割示例

```powershell
# 假设微信长截图宽度是 1080，每 2000 像素高度切一张
magick "聊天记录.png" -crop 1080x2000 +repage +adjoin "聊天_%02d.png"
# 输出: 聊天_00.png, 聊天_01.png, 聊天_02.png ...
```

---

## 📏 调整大小 (Resize)

### 按像素调整

```powershell
# 调整到 800x600 (可能变形)
magick input.png -resize 800x600! output.png

# 调整到 800x600 以内 (保持比例)
magick input.png -resize 800x600 output.png

# 只指定宽度，高度自动计算
magick input.png -resize 800x output.png

# 只指定高度，宽度自动计算
magick input.png -resize x600 output.png
```

### 按百分比调整

```powershell
# 缩小到 50%
magick input.png -resize 50% output.png

# 放大到 200%
magick input.png -resize 200% output.png
```

### 缩略图 (Thumbnail)

```powershell
# 生成 200x200 缩略图 (更高效，会丢弃元数据)
magick input.png -thumbnail 200x200 output.png
```

---

## 🔄 格式转换 (Convert)

### 基本转换

```powershell
# PNG 转 JPG
magick input.png output.jpg

# JPG 转 PNG
magick input.jpg output.png

# 转 WebP (更小体积)
magick input.png output.webp

# 转 GIF
magick input.png output.gif
```

### 批量转换

```powershell
# 当前目录所有 PNG 转 JPG
magick mogrify -format jpg *.png

# 当前目录所有 JPG 转 WebP
magick mogrify -format webp *.jpg
```

---

## 🖼️ 图片拼接 (Montage / Append)

### 垂直拼接

```powershell
# 垂直拼接多张图片
magick 1.png 2.png 3.png -append output.png

# 垂直拼接当前目录所有 PNG
magick *.png -append output.png
```

### 水平拼接

```powershell
# 水平拼接多张图片
magick 1.png 2.png 3.png +append output.png
```

### 网格拼接 (Montage)

```powershell
# 2x2 网格拼接
magick montage 1.png 2.png 3.png 4.png -tile 2x2 -geometry +0+0 output.png

# 3x3 网格拼接，每张图 200x200
magick montage *.png -tile 3x3 -geometry 200x200+5+5 output.png

# 单列拼接 (1xN)
magick montage *.png -tile 1x -geometry +0+0 output.png

# 单行拼接 (Nx1)
magick montage *.png -tile x1 -geometry +0+0 output.png
```

---

## 🎨 图片处理

### 旋转

```powershell
# 顺时针旋转 90 度
magick input.png -rotate 90 output.png

# 逆时针旋转 90 度
magick input.png -rotate -90 output.png

# 旋转 180 度
magick input.png -rotate 180 output.png
```

### 翻转

```powershell
# 垂直翻转 (上下颠倒)
magick input.png -flip output.png

# 水平翻转 (左右镜像)
magick input.png -flop output.png
```

### 添加边框

```powershell
# 添加 10 像素白色边框
magick input.png -bordercolor white -border 10 output.png

# 添加 20 像素黑色边框
magick input.png -bordercolor black -border 20 output.png
```

### 调整质量/压缩

```powershell
# 输出 JPG 质量 85 (默认约 92)
magick input.png -quality 85 output.jpg

# 输出 WebP 质量 80
magick input.png -quality 80 output.webp
```

### 灰度化

```powershell
magick input.png -colorspace Gray output.png
```

### 反色

```powershell
magick input.png -negate output.png
```

---

## 📊 查看图片信息

```powershell
# 查看图片基本信息 (格式、尺寸、色彩空间等)
magick identify input.png

# 查看详细信息
magick identify -verbose input.png

# 只查看尺寸
magick identify -format "%wx%h" input.png
```

---

## 🔧 批量处理 (Mogrify)

> ⚠️ `mogrify` 会直接修改原文件！建议先备份。

```powershell
# 批量调整大小
magick mogrify -resize 800x *.png

# 批量转格式
magick mogrify -format jpg *.png

# 批量添加边框
magick mogrify -bordercolor white -border 10 *.png

# 批量压缩质量
magick mogrify -quality 80 *.jpg
```

---

## 📋 参数速查表

| 参数 | 说明 | 示例 |
|------|------|------|
| `-crop WxH+X+Y` | 裁剪指定区域 | `-crop 800x600+100+50` |
| `-crop NxM@` | 切成 N 列 M 行网格 | `-crop 2x3@` |
| `-resize WxH` | 调整大小 (保持比例) | `-resize 800x600` |
| `-resize WxH!` | 强制调整大小 (可能变形) | `-resize 800x600!` |
| `-resize N%` | 按百分比调整 | `-resize 50%` |
| `-rotate N` | 旋转 N 度 | `-rotate 90` |
| `-quality N` | 输出质量 (1-100) | `-quality 85` |
| `-density N` | DPI 设置 | `-density 300` |
| `-append` | 垂直拼接 | `1.png 2.png -append` |
| `+append` | 水平拼接 | `1.png 2.png +append` |
| `-tile NxM` | montage 网格布局 | `-tile 3x3` |
| `-trim` | 去除边缘空白 | `-trim +repage` |
| `+repage` | 重置画布信息 | 切割后常用 |
| `+adjoin` | 分离输出多个文件 | 切割时必须 |
| `-format` | mogrify 转换格式 | `-format jpg` |

---

## 💡 常见场景

### 场景1：微信长截图切割

```powershell
# 1. 查看图片尺寸
magick identify "长截图.png"

# 2. 按固定高度切割 (假设每 2000 像素)
magick "长截图.png" -crop x2000 +repage +adjoin "切片_%02d.png"
```

### 场景2：多张截图拼成一张长图

```powershell
magick 1.png 2.png 3.png 4.png -append 长图.png
```

### 场景3：批量生成缩略图

```powershell
# 创建 thumbs 目录
mkdir thumbs

# 生成 200x200 缩略图
Get-ChildItem *.jpg | ForEach-Object {
    magick $_.Name -thumbnail 200x200 "thumbs\$($_.BaseName)_thumb.jpg"
}
```

### 场景4：PDF 转图片

> 详见 `PDF转图片\PDF转图片工具说明.md`

```powershell
magick -density 300 input.pdf output_%d.png
```
