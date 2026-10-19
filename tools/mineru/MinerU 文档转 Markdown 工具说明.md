# MinerU 文档转 Markdown 工具说明 v2.1

## ⚠️ 重要提醒

**API Key 有效期为 90 天！** 当前 Token 到期时间：**2026-06-02**
如果转换时报错（如 Token 过期），请访问 [MinerU官网](https://mineru.net) 更新 Token，并修改脚本中的 `DEFAULT_API_TOKEN`。

---

## 🚀 简介

这是一个全功能的 MinerU 客户端，支持将 **PDF / Word / PPT / 图片 / 网页 (URL)** 转换为高质量的 **Markdown**。

**v2.1 更新亮点**:
- **🧠 智能模型选择**：自动根据输入类型（文档 vs 网页）选择最佳 AI 模型（VLM / MinerU-HTML）。
- **🧩 混合批次处理**：**支持一次性提交 PDF、Word 和 网页 URL**，脚本会自动分组处理，无需分开运行。
- **全格式支持**：除了 Markdown，还支持导出 HTML、Word、LaTeX。

## 🛠️ 快速开始

### 1. 极简模式（推荐）

这是最常用的方式，什么参数都不用管，直接转。**即使同时输入 PDF 和 URL 也没问题！**

```powershell
# 混合输入示例：同时转换一个 PDF 和一个网页
python mineru_pdf2md.py "d:\test.pdf" "https://baike.baidu.com/item/机器人"
```

脚本会自动判断：
- `test.pdf` -> 使用 VLM 模型 (文档效果最好)
- `https://...` -> 使用 MinerU-HTML 模型 (网页解析专用)

默认输出路径：`D:\Antigravity-Hub\temp\MinerU转换\{文件名}\`

### 2. 高级模式

当你需要更多控制时（比如只转前10页，或者想关掉电脑过会儿再看）。

**常用参数说明**：
- `--pages "1-5"`：只转换第1到5页
- `--no-wait`：**异步模式**。提交任务后立刻退出，不等待结果（适合大批量大文件）。
- `-e html docx`：额外导出 html 和 word 格式。
- `--language en`：指定文档语言为英文（默认 `ch` 中文）。

**示例命令**：

```powershell
# 场景：文档有500页，只要前10页，且导出 Word 格式
python mineru_pdf2md.py "d:\big_book.pdf" --pages "1-10" -e docx

# 场景：批量提交 URL，不等结果（异步）
python mineru_pdf2md.py submit "http://url1.com" "http://url2.com" --no-wait
# (运行后会返回一个或多个 Batch ID)

# 场景：查询异步任务结果
python mineru_pdf2md.py query "12345abcdef"
```

---

## 📚 参数详解

该脚本支持两个子命令：`submit` (默认) 和 `query`。

### `submit` 命令

用于创建新的转换任务。

| 参数 | 简写 | 描述 | 默认值 |
| :--- | :--- | :--- | :--- |
| `inputs` | - | 输入文件路径或 URL (支持多种类型混合) | 必填 |
| `--output` | `-o` | 输出目录 | `D:\Antigravity-Hub\temp\MinerU转换` |
| `--model` | `-m` | 强制指定模型 (`vlm`/`MinerU-HTML`) | **自动智能选择** |
| `--extra-formats` | `-e` | 额外导出格式 (`html` `docx` `latex`) | 无 |
| `--pages` | - | 页码范围 (如 `1-10,20`) | 全部 |
| `--language` | - | OCR 主要语言 | `ch` |
| `--no-wait` | - | 异步模式，提交即退出 | 关闭 |

**关于 `--model` 参数**：一般情况下请**不要**手动指定，脚本会自动为文档选 VLM，为网页选 HTML。除非由于某种原因自动判断错误，你才需要强制指定。

### `query` 命令

用于查询历史任务（特别是用 `--no-wait` 提交的任务）。

```powershell
python mineru_pdf2md.py query <Batch_ID>
```

---

## 📂 目录结构与命名规范

### 子目录命名规则（确定性映射）

与 PDF转图片 工具一致：取源文件完整路径，去掉盘符和扩展名，将路径分隔符 `\` 替换为 `_`。

- 例：`D:\TJU-Notes\大学课程\大二下\数据库原理与应用\课件\pdf\ch1.pdf`
  → 文件夹名：`TJU-Notes_大学课程_大二下_数据库原理与应用_课件_pdf_ch1`
- URL 输入仍使用 URL 衍生的文件名

```
D:\Antigravity-Hub\temp\MinerU转换\
└── TJU-Notes_大学课程_大二下_数据库原理与应用_课件_pdf_ch1\
    ├── ch1.md                 <-- 主内容
    ├── ch1.assets\            <-- 图片文件夹（Typora 兼容）
    ├── ch1.docx               <-- (如果有选择导出)
    └── ch1.html               <-- (如果有选择导出)
```

### 转换流程（缓存优先）

> ⚠️ **必须先检查缓存，避免重复转换浪费 API 配额。**

脚本已内置缓存检查：对于本地文件，会自动检查目标文件夹是否已存在且含 `.md` 文件。
已缓存的文件会自动跳过，不会上传和消耗配额。

## 📝 常见问题

1.  **URL 解析失败？**
    *   确保 URL 是公开可访问的。
    *   脚本会自动识别 URL 是否为网页。如果 URL 没有后缀但确实是网页，脚本也会尝试用 HTML 模型解析。

2.  **报错 "Token expired"？**
    *   去官网重新生成 Token，并在脚本头部修改 `DEFAULT_API_TOKEN`。
