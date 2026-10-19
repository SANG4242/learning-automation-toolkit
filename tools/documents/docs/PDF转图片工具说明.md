# PDF 转图片工具说明

## 已安装工具

- **ImageMagick** 7.1.2-Q16-HDRI（图像处理引擎）
- **Ghostscript** 10.6.0（PDF 解析器，ImageMagick 依赖它来读取 PDF）

## 安装路径

- ImageMagick: `C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\`
- Ghostscript: `C:\ProgramData\chocolatey\lib\Ghostscript`

## 使用方法

### 推荐：使用 Python 脚本（自动 DPI + 缓存检查）

```powershell
# 默认用法：auto 吃满 1500px + JPG q85
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf"

# 多文件输入
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "文件1.pdf" "文件2.pdf" "文件3.pdf"

# 目录输入（自动收集目录下所有 .pdf 文件）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\某个目录"

# 指定 JPG 质量（降低质量以减小体积）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" -q 60

# 指定目标分辨率（长边像素数）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" --target 1200

# 手动指定 DPI（禁用自动计算）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" --density 150

# 输出 PNG 格式
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" -f png

# 强制重新转换（忽略缓存）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" --force

# 转换后自动拼接（4张一页，JPG格式）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" --stitch

# 转换后自动拼接（6张一页）
python "D:\Antigravity-Hub\工具脚本\PDF转图片\pdf2img.py" "D:\路径\文件.pdf" --stitch 6
```

### 默认行为

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 模式 | auto | 自动根据 PDF 页面尺寸计算 DPI，让长边吃满目标像素 |
| target | 1500px | 长边目标像素数（Claude 推荐上限 1568px） |
| format | jpg | 输出格式（jpg 比 png 体积小 60%+） |
| quality | 85 | JPG 压缩质量（对 AI 识别无影响，q30~q85 效果完全一样） |
| stitch | 关闭 | 可选，转完后自动调用拼接工具（preset 4 或 6） |

### auto 模式原理

PDF 是矢量格式，没有固定像素。转图片需要指定 DPI：

```
输出像素 = PDF 页面物理尺寸（英寸）× DPI
```

auto 模式反向计算：

```
最优 DPI = 目标像素（1500）÷ 页面长边（英寸）
```

不同尺寸 PDF 的自动 DPI：

| PDF 类型 | 页面尺寸 | 自动 DPI | 输出像素 |
|---------|---------|---------|---------|
| PPT 4:3 | 10 × 7.5 英寸 | 150 | 1500 × 1125 |
| PPT 16:9 | 13.33 × 7.5 英寸 | 112 | 1500 × 843 |
| A4 | 8.27 × 11.69 英寸 | 128 | 1059 × 1500 |

## 输出路径规范

- **统一输出目录**：`D:\Antigravity-Hub\temp\PDF转图片\`
- **子目录命名规则（确定性映射）**：
  - 取源文件完整路径，去掉盘符和扩展名，将路径分隔符 `\` 替换为 `_`
  - 例：`D:\TJU-Notes\大学课程\大二下\操作系统\课件\PDF\ch2 硬件环境.pdf`
    → 文件夹名：`TJU-Notes_大学课程_大二下_操作系统_课件_PDF_ch2 硬件环境`
- **图片命名格式**：`页码.jpg`（从 1 开始，如 `1.jpg`, `2.jpg`）

### 缓存机制

> 脚本内置缓存检查，目标目录已有同格式图片则自动跳过。
> 如需强制重新转换，使用 `--force` 参数。

### 32MB 超限提示

> 转换完成后自动检查总大小。如果超过 Claude 的 32MB 上限，会提示降低质量或分辨率。

## Claude 图片处理参数参考

| 项目 | 值 |
|------|------|
| 最佳分辨率范围 | 200px ~ 1568px（每边） |
| 超过 1568px | 自动缩放到 1568px 以内 |
| 最大分辨率 | 8000 × 8000 px |
| 单次请求总大小 | 32 MB |
| 支持格式 | JPEG, PNG, GIF, WebP |

### 质量与体积实测数据（PPT 课件，每页）

| 方案 | 单页大小 | 50 页 | 200 页 | AI 识别 |
|------|---------|-------|--------|--------|
| 1500px q85 | ~130 KB | ~6.3 MB | ~25.4 MB | ✅ 清晰 |
| 1500px q75 | ~120 KB | ~5.9 MB | ~23.4 MB | ✅ 清晰 |
| 1500px q60 | ~100 KB | ~4.9 MB | ~19.5 MB | ✅ 清晰 |
| 1200px q85 | ~110 KB | ~5.4 MB | ~21.5 MB | ✅ 清晰 |
| 1200px q60 | ~75 KB | ~3.7 MB | ~14.6 MB | ✅ 清晰 |

> 结论：对 AI 识别来说，q30~q85、800px~1500px 范围内效果完全一样。
> 降低参数只影响文件体积，不影响识别质量。

## 注意事项

1. 如果命令 `magick` 无法识别，需要重启终端或使用完整路径：
   ```powershell
   & "C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe" -density 300 input.pdf output.png
   ```

2. 安装日期：2026-01-11
3. 通过 Chocolatey 安装
