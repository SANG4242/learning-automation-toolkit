# 图片拼接工具使用说明

## 📌 简介

`image_stitcher.py` 是一个命令行图片拼接工具，用于将多张图片拼接成网格布局的大图。

**主要用途**：当AI无法通过 `view_file` 查看图片时，可以使用此工具将多张图片拼接成一张，减少手动上传次数。

## 🚀 快速使用

```bash
# 最简单的用法（拼接当前目录下的所有图片）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "图片所在目录"

# 指定输出文件名前缀
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\第11章.assets" -p "第11章_存储器"

# 选择特定图片（按序号）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --select 7-9,24

# 选择特定图片（按文件名匹配）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --filter "*等价类*"

# 直接指定文件名（支持模糊匹配）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --files "等价类示例图_R1,最大元最小元示例图"
```

## 📋 参数说明

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--input` | `-i` | `.` (当前目录) | 输入图片目录路径 |
| `--output` | `-o` | 输入目录下的 `拼接结果` | 输出目录路径 |
| `--prefix` | `-p` | `拼接图片` | 输出文件名前缀 |
| `--preset` | - | `6` | 布局预设：`6`（每页6张）或 `4`（每页4张更清晰） |
| `--auto-size` | - | False | **自动按源图宽高比计算 cell_height**，消除竖版图片两侧空白（推荐用于 PDF 转图片场景） |
| `--cols` | `-c` | `2` | 每行列数 |
| `--rows` | `-r` | `3` 或 `2` | 每页行数（取决于预设） |
| `--theme` | `-t` | `light` | 主题配色：`light`（白底黑字）或 `dark`（深色背景） |
| `--select` | `-s` | 无 | **按序号选择图片**，支持范围和逗号分隔 |
| `--filter` | `-f` | 无 | **按文件名通配符匹配** |
| `--files` | - | 无 | **直接指定文件名**（逗号分隔，支持模糊匹配） |
| `--cell-width` | - | `1000` | 单元格宽度（像素） |
| `--cell-height` | - | `620` 或 `950` | 单元格高度（像素，取决于预设） |
| `--no-label` | - | False | 添加此参数则不显示图片名称标签 |
| `--padding` | - | `20` | 图片间距（像素） |
| `--font-size` | - | `36` | 标签字体大小 |
| `--format` | - | `jpg` | 输出格式：`png` 或 `jpg`（jpg 体积约为 png 的 1/3） |
| `--quality` | - | `85` | JPG 压缩质量 1-100（仅 `--format jpg` 时有效） |

## 🔍 筛选功能详解

### --select 按序号选择

按图片的序号选择要拼接的图片（1-indexed，即从1开始计数）。

**支持的格式**：
- 单个数字：`7` → 选择第7张
- 逗号分隔：`7,9,24` → 选择第7、9、24张
- 范围：`7-9` → 选择第7、8、9张
- 混合：`7-9,24,30-32` → 选择第7-9张和第24张、第30-32张

**示例**：
```bash
# 选择第7-9张和第24张图片
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" -s 7-9,24

# 只选择第1张和第10张
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --select 1,10
```

### --filter 按文件名匹配

按文件名通配符模式筛选图片。

**通配符说明**：
- `*` 匹配任意字符（包括空）
- `?` 匹配单个字符

**示例**：
```bash
# 选择文件名包含"等价类"的图片
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" -f "*等价类*"

# 选择以"01_"开头的图片
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --filter "01_*"

# 选择所有哈斯图相关的图片
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" -f "*哈斯图*"
```

### --files 直接指定文件名 ⭐ 推荐

直接指定文件名列表，用逗号分隔。**支持模糊匹配**，更加灵活易用！

**匹配规则（按优先级）**：
1. **完全匹配**（包含扩展名）：`07_等价类示例图_R1.jpg`
2. **不含扩展名匹配**：`07_等价类示例图_R1`
3. **忽略序号前缀匹配**：`等价类示例图_R1`（会匹配到 `07_等价类示例图_R1.jpg`）
4. **包含关系匹配**：`等价类示例图` 会匹配到 `07_等价类示例图_R1.jpg`

**示例**：
```bash
# 直接指定文件名（可以省略序号前缀和扩展名）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\4.4.assets" --files "等价类示例图_R1,等价类示例图_R2,最大元最小元示例图"

# 使用完整文件名
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --files "07_等价类示例图_R1.jpg,24_最大元最小元示例图.jpg"

# 使用部分文件名（模糊匹配）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --files "R1,R2,最大元"
```

**优势**：
- ✅ 不需要记住图片序号
- ✅ 可以省略扩展名（.jpg、.png等）
- ✅ 可以省略开头的序号前缀（如 `07_`）
- ✅ 支持部分名称匹配

## 📝 使用示例

### 1. 基础用法（拼接所有图片）

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\第11章.assets"
```

输出：`d:\课件\第11章.assets\拼接结果\拼接图片_第1页.png` ...

### 2. 指定输出前缀

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\第11章.assets" -p "第11章_存储器"
```

输出：`拼接结果\第11章_存储器_第1页.png` ...

### 3. 使用4张预设（更高清晰度）

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --preset 4
```

### 4. 使用深色主题

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --theme dark
```

### 5. 选择特定图片

```bash
# 按序号选择（选择第7-9张和第24张）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\4.4.assets" -s 7-9,24 -p "待确认图片"

# 按文件名匹配（选择包含"哈斯图"的图片）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\4.4.assets" -f "*哈斯图*"

# 直接指定文件名（最灵活的方式）
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\4.4.assets" --files "等价类示例图_R1,R2,R3,最大元最小元示例图"
```

### 6. 不显示标签

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --no-label
```

### 7. PDF 转图片后自适应拼接 ⭐ 推荐

适用于 PDF 页面是竖版（如教材、课件）的场景。固定格子尺寸与页面比例不符，会产生两侧大量空白；`--auto-size` 会读取第一张图的实际宽高比，自动计算 cell_height，让每张页面充满格子。

```bash
# PDF 转图后自适应拼接（消除竖版页面两侧空白）
python image_stitcher.py -i "图片目录" --preset 4 --auto-size --no-label
```

> ⚠️ `--auto-size` 会改变总画布高度（格子变高 → 画布变高），正常现象。

### 8. 自定义单元格大小

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件" --cell-width 1200 --cell-height 800
```

### 9. 指定输出目录

```bash
python d:\TJU-Notes\工具脚本\image_stitcher.py -i "d:\课件\第11章.assets" -o "d:\输出"
```

## 📁 输出说明

- **默认输出目录**：在输入图片目录下创建 `拼接结果` 子文件夹
- **输出文件命名**：`{前缀}_第{页码}页.png`
- **支持的图片格式**：jpg, jpeg, png, gif, bmp, webp
- **排序方式**：按文件名开头的数字排序（如 `01_xxx.png`, `02_xxx.png`）

## 🎨 主题说明

| 主题 | 背景色 | 标签背景 | 文字颜色 |
|------|--------|----------|----------|
| `light` (默认) | 白色 | 浅灰 | 黑色 |
| `dark` | 深蓝黑 | 深蓝 | 浅灰 |

## 📐 预设说明

| 预设 | 布局 | 每页图片数 | 单元格大小（默认） | 适用场景 |
|------|------|-----------|-----------|----------|
| `6` (默认) | 2列×3行 | 6张 | 1000×620 | 平衡数量与清晰度 |
| `4` | 2列×2行 | 4张 | 1000×950 | 更高清晰度，适合复杂图表 |

> 💡 加 `--auto-size` 后，cell_height 会根据源图宽高比自动覆盖预设值，总画布高度随之变化。

## ⚠️ 注意事项

1. 运行前需要安装 Pillow 库：`pip install Pillow`
2. 脚本会自动过滤输出目录（`拼接结果`）中的图片
3. 图片按文件名开头的数字排序，没有数字的排在最后
4. `--select` 使用 1-indexed（从1开始计数）
5. `--select`、`--filter` 和 `--files` 可以单独使用
6. 如果同时使用多个筛选条件，会依次应用（先select，再filter，最后files）

## 🔧 依赖

- Python 3.6+
- Pillow (PIL)

```bash
pip install Pillow
```
