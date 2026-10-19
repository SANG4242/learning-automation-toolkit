# 文档格式转换工具说明

## 工具概览

| 脚本 | 功能 | 适用场景 |
|------|------|----------|
| **docx2pdf.py** | docx/doc → PDF | Gemini 等可直接看 PDF 的模型 |
| **ppt2pdf.py** | pptx/ppt → PDF | Gemini 等可直接看 PDF 的模型 |
| **doc2img.py** | docx/doc → JPG 图片（一步到位） | Claude 等不能看 PDF 的模型 |
| **ppt2img.py** | pptx/ppt → JPG 图片（一步到位） | Claude 等不能看 PDF 的模型 |

### 架构

```
第一层：Office → PDF（独立使用）
  docx2pdf.py ── 默认 WPS；可选 Word / LibreOffice → PDF
  ppt2pdf.py  ── 默认 PowerPoint；可选 WPS / LibreOffice → PDF

第二层：PDF → 图片（独立使用）
  pdf2img.py  ── ImageMagick + Ghostscript → JPG/PNG

第三层：Office → 图片（一步到位，组合第一层 + 第二层）
  doc2img.py  ── 调用 docx2pdf → 调用 pdf2img → 图片
  ppt2img.py  ── 调用 ppt2pdf → 调用 pdf2img → 图片
```

图片参数（DPI、质量、格式、32MB 提示）**只在 pdf2img.py 维护一处**。
引擎选择、COM/LibreOffice 导出与 PDF 缓存逻辑集中在 `docx2pdf.py`；`ppt2pdf.py` 复用该核心，两个转图片入口分别导入对应 PDF 模块。

## 依赖

- **Python**：四个转换入口无需额外 Python 包。
- **WPS 引擎**：安装 WPS 并注册 `KWPS.Application`（文字）或 `KWPP.Application`（演示）；通过 PowerShell 调用 COM。
- **Office 引擎**：Word 文档需要 Microsoft Word，演示文稿需要 Microsoft PowerPoint；通过 PowerShell 调用 COM。
- **LibreOffice 引擎**：需要 `soffice.com` 或 `soffice.exe`，无需 Microsoft Office；使用独立用户配置目录进行无界面转换。
- **图片链路**：另需 ImageMagick、Ghostscript 和 `pdf2img.py`。

## 转换引擎与参数

| 入口 | 默认参数 | 实际引擎 |
|------|----------|----------|
| `docx2pdf.py` | `--engine wps` | WPS 文字 |
| `ppt2pdf.py` | `--engine office` | Microsoft PowerPoint |
| `doc2img.py` | `--engine office` | Microsoft Word |
| `ppt2img.py` | `--engine office` | Microsoft PowerPoint |

四个入口分别设置默认值；`doc2img.py` 保持 Word 默认，不跟随 `docx2pdf.py` 的 WPS 默认。

| 参数 | 行为 | 默认值 |
|------|------|--------|
| `--engine` | `wps`、`office`、`libreoffice`、`auto`；日志显示实际引擎 | 按上表 |
| `--timeout` | 正整数秒数；COM 为整个批次的等待上限，LibreOffice 为每个文件的等待上限 | COM：`max(120, 60 × 文件数)`；LibreOffice：120 秒 |
| `--libreoffice-path` | 指定 `soffice.com` 或 `soffice.exe` 路径 | 检查 PATH、本机 `D:\Apps\LibreOffice\program\soffice.com` 和 Program Files 常见路径 |

`auto` 按 WPS → Office → LibreOffice 的可用性选择：COM 引擎检查注册项，LibreOffice 检查程序路径。选择后转换失败直接报告，不在运行中切换引擎。明确指定引擎时也不会自动切换。

```powershell
python 'D:\Antigravity-Hub\工具脚本\文档格式转换\docx2pdf.py' 'D:\资料\说明.docx' --engine office
python 'D:\Antigravity-Hub\工具脚本\文档格式转换\doc2img.py' 'D:\资料\说明.docx' --engine wps
python 'D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2pdf.py' 'D:\资料\课件.pptx' --engine libreoffice --timeout 180
```

其他参数通过对应脚本的 `--help` 查询。不同引擎可能采用不同的字体替补和排版规则，交付前仍需查看实际页面。

## 通用功能

所有脚本均支持以下输入方式：

```powershell
# 单文件
python script.py "D:\路径\文件.docx"

# 多文件
python script.py "文件1.docx" "文件2.doc"

# 目录批量（自动扫描所有目标格式文件）
python script.py "D:\某个目录"

# 通配符筛选（选择目录中的部分文件）
python script.py "D:\某个目录\No.9*"
python script.py "D:\某个目录\ch[1-3]*"

# 强制重新转换（忽略缓存）
python script.py "文件.docx" --force
```

## 使用方法

### docx2pdf.py — Word 转 PDF

```powershell
# 默认输出（路径命名 → temp 目录）
python "D:\Antigravity-Hub\工具脚本\文档格式转换\docx2pdf.py" "文件.docx"

# 指定输出目录 + 保持原文件名
python "D:\Antigravity-Hub\工具脚本\文档格式转换\docx2pdf.py" "D:\某目录" -o "D:\输出目录"

# 通配符：只转部分文件
python "D:\Antigravity-Hub\工具脚本\文档格式转换\docx2pdf.py" "D:\某目录\No.9*"
```

### ppt2pdf.py — PPT 转 PDF

```powershell
# 默认输出（路径命名 → temp 目录）
python "D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2pdf.py" "文件.pptx"

# 指定输出目录 + 保持原文件名
python 'D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2pdf.py' 'D:\某目录' -o 'D:\输出目录'

# 通配符：只转部分文件
python "D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2pdf.py" "D:\某目录\ch7*"
```

### doc2img.py — Word 转图片（一步到位）

```powershell
# 默认：auto 吃满 1500px + JPG q85
python "D:\Antigravity-Hub\工具脚本\文档格式转换\doc2img.py" "D:\路径\文件.docx"

# 指定 JPG 质量
python "D:\Antigravity-Hub\工具脚本\文档格式转换\doc2img.py" "文件.docx" -q 60

# 通配符 + 强制重新转换
python "D:\Antigravity-Hub\工具脚本\文档格式转换\doc2img.py" "D:\某目录\No.9*" --force
```

### ppt2img.py — PPT 转图片（一步到位）

```powershell
# 默认：auto 吃满 1500px + JPG q85
python "D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2img.py" "D:\路径\文件.pptx"

# 指定 JPG 质量
python "D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2img.py" "文件.pptx" -q 60

# 通配符筛选
python "D:\Antigravity-Hub\工具脚本\文档格式转换\ppt2img.py" "D:\某目录\ch[1-3]*"
```

### 通用透传参数（doc2img / ppt2img 均支持）

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-q` / `--quality` | JPG 质量 1~100 | 85（由 pdf2img.py 决定） |
| `--target` | auto 模式目标长边像素 | 1500 |
| `--density` | 手动指定 DPI（禁用 auto） | 无（auto） |
| `-f` / `--format` | 输出格式 png/jpg | jpg |
| `--no-auto` | 禁用自动 DPI 计算 | 开启 auto |
| `--force` | 忽略缓存强制重转 | 不强制 |

### Word 转换输出参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o` / `--output` | `docx2pdf.py` 指定PDF目录或单文件路径；`doc2img.py` 指定图片目录 | 对应 temp 目录 |
| `--names` | 依次指定输出PDF名称或图片子目录名，数量须与收集到的文件一致 | 路径命名 |

`docx2pdf.py` 指定自定义输出目录时默认保留原文件名。

### PPT 转 PDF 输出参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o` / `--output` | 指定 PDF 目录或单文件 PDF 路径；自定义目录保留原名 | temp 目录，路径命名 |
| `--names` | 依次指定 PDF 文件名，数量须与收集到的文件一致 | 路径命名或按输出目录保留原名 |

## 输出路径规范

### 命名规则

| 模式 | 规则 | 适用场景 |
|------|------|----------|
| **路径命名法**（默认） | 完整路径 → 去盘符、去扩展名、`\` → `_` | 输出到默认 temp 目录，避免同名冲突 |
| **保持原名** | 保留原始文件名，仅改扩展名 | 转 PDF 指定 `-o` 输出到自定义目录 |
| **指定名称** | 按 `--names` 顺序设置文件名或图片子目录名 | 需要明确命名时 |

**路径命名法示例：**

源文件：`D:\TJU-Notes\大学课程\大二下\操作系统\课件\PDF\ch2 硬件环境.pptx`

| 输出 | 路径 |
|------|------|
| 中间 PDF | `temp\PPT转PDF\TJU-Notes_大学课程_大二下_操作系统_课件_PDF_ch2 硬件环境.pdf` |
| 图片 | `temp\PDF转图片\TJU-Notes_..._ch2 硬件环境\1.jpg, 2.jpg, ...` |

### 统一输出目录

| 类型 | 目录 |
|------|------|
| Word 中间 PDF | `D:\Antigravity-Hub\temp\Word转PDF\` |
| PPT 中间 PDF | `D:\Antigravity-Hub\temp\PPT转PDF\` |
| 图片（所有来源共用） | `D:\Antigravity-Hub\temp\PDF转图片\` |

## 缓存机制

- **docx2pdf / ppt2pdf**：缓存记录源文件路径、大小、修改时间，实际引擎及输出 PDF 的大小、修改时间；LibreOffice 另记录程序路径。签名一致才跳过，切换引擎会重新转换。
- **缓存位置**：`D:\Antigravity-Hub\temp\杂项\office_conversion_cache\`，不会在交付目录生成额外 JSON。未带签名的旧 PDF 首次使用新规则时重新转换。
- **doc2img / ppt2img**：复用同一 PDF 缓存规则；本次 PDF 重转成功后，强制刷新对应图片。PDF 未重转时沿用 `pdf2img.py` 的图片缓存。
- **pdf2img.py**：独立运行时，目标目录已有同格式图片会跳过；直接替换 PDF 后应使用 `--force`，并按页面验收指引检查当前预览。
- 所有脚本均支持 `--force` 忽略缓存；图片参数变化时可用它重新生成预览。

## 批量转换优化

COM 引擎复用同一个 Word、PowerPoint 或 WPS 实例处理一个批次。LibreOffice 按文件依次执行，批次内复用独立配置目录。自动化实例已有文档时停止转换并报告，原有文档保持不变。

## 32MB 超限提示

转换完成后 pdf2img.py 自动检查总大小：
- 超过 32MB → 提示降低 `--quality` 或 `--target`
- 接近 80%（25.6MB）→ 提醒留意空间

## 路径与结果检查

Word 入口支持 `.doc`、`.docx`，PPT 入口支持 `.ppt`、`.pptx`。COM 引擎只读打开原件、禁用宏，通过编码后的 JSON 传递源路径和输出路径；LibreOffice 通过参数列表调用。两类方式均避免将文件路径直接拼入命令脚本。

PowerShell 命令入口使用 ASCII 单引号包裹含中文引号的路径，也可从目录取得路径后通过变量传入：

```powershell
python 'D:\Antigravity-Hub\工具脚本\文档格式转换\doc2img.py' 'D:\资料\“申请表”.doc'

$files = @(Get-ChildItem -LiteralPath 'D:\资料' -File -Filter '附件1*.doc' | ForEach-Object { $_.FullName })
python 'D:\Antigravity-Hub\工具脚本\文档格式转换\docx2pdf.py' @files
```

文件名含 ASCII 单引号时，优先使用变量传入。四个入口全部成功返回 0，转换失败或无有效输入返回 1，参数解析错误返回 2。转换错误显示文件信息、引擎输出或退出码；生成的 PDF 先在工作目录检查存在、非空及 `%PDF-` 文件头，导出验证通过后才替换目标 PDF。实际导出失败时保留已有目标文件。此检查不代替内容与页面验收。

## 已知限制与超时处理

- COM 超时会显示最后记录的打开或导出阶段；外部应用可能仍在运行，脚本不会按进程名批量结束 Office/WPS。先核对应用状态和本次自动化实例，取得授权后只清理已确认的测试进程，再重试或显式指定其他引擎。
- 旧格式 `.ppt` 样本曾在 WPS 打开阶段超时；清理本次自动化进程后重试成功，根因未确定。PPT 默认仍为 PowerPoint。
- 本机 LibreOffice 转换时出现 `Document is empty` 和 Python 库路径警告，但测试样本均生成了可读取的 PDF。脚本保留警告，结合返回码和 PDF 检查判断结果；交付前仍需核对页面。
- 不同引擎的字体替补与版式可能不同。脚本保持原件内容，不主动统一字体；选用引擎后应检查字体、粗体、分页、表格和文字完整性。

## 验证记录

### 2026-10-12：多引擎与缓存验证

- 中文 Word 作业说明经 Word、WPS、LibreOffice 转换均为 9 页；WPS 中文字体统一为宋体，与原件正文的 5,523 个汉字计数一致，全部页面预览未发现裁切或重叠。该样本支持将 `docx2pdf.py` 默认设为 WPS；其他三个入口保持 Office 默认。
- WPS 批量转换中英文 Word 说明成功，分别为 9 页和 10 页；中文 `.pptx` 样本三种引擎均导出为 49 页。旧 `.ppt` 样本经 PowerPoint 和 WPS 导出均为 65 页，WPS 超时及重试情况见上节。
- 两个转图片入口的 Office 默认、WPS 可选引擎、切换引擎后的图片刷新及重复运行的缓存命中已验证。PDF 引擎切换会重新转换。
- 中文、单引号和美元符号路径，缺失输入、非正数超时、无效 LibreOffice 路径的退出码检查通过；实际 COM 打开失败返回失败且已有 PDF 内容不变；模拟超时能显示最后阶段。LibreOffice 控制台中文编码处理已验证。
- 旧 PPT 测试结束后，未发现本次测试遗留的 WPS 自动化进程。测试输出位于 `D:\Antigravity-Hub\temp\杂项\office_engine_compare_20261012\`，课程原件和已有作业 PDF 未改动。

### 2026-10-02：Word 路径与批量验证

两份文件名含中文引号的申请表 DOC 批量转 PDF 成功；Word 转图片链路成功；模拟特殊字符路径、PowerShell 失败输出、临时脚本清理和无有效输入退出码检查通过。

## 注意事项

1. 转换会启动所选 Office/WPS 或 LibreOffice 实例，正常完成后退出本次实例；超时处理见上节。
2. 图片编号从 `1` 开始，如 `1.jpg`、`2.jpg`，背景为白色。
3. 中间 PDF 保留在对应 temp 目录，供后续阅读或转图片复用。
4. 图片参数由 `pdf2img.py` 统一维护，两个转图片入口通过导入对应 PDF 模块复用转换逻辑。
5. `doc2img.py` 默认 Word；需要与默认 WPS 的 `docx2pdf.py` 输出一致时，显式传入 `--engine wps`。
