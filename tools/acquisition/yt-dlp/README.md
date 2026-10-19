# yt-dlp 使用指南

> yt-dlp 已全局安装（v2026.3.17），可直接在命令行调用。

---

## YouTube 反爬前置条件（2026.06 更新）

YouTube 加强了 JS 签名验证与 bot 拦截，yt-dlp 访问 YouTube 推荐使用以下组合：

1. **Firefox 自动读取 cookies（首选方案，免手动更新）**：使用 `--cookies-from-browser firefox` 参数。只需在 Firefox 浏览器登录一次 YouTube 账号即可。yt-dlp 会直接读取其 SQLite 数据库，并随着登录态自动轮换 token，无需手动导出。
2. **deno 运行时**：已安装到 `~/.deno/bin/deno.exe`。yt-dlp 会自动调用，**但 Antigravity 终端需手动加 PATH**：在命令前加 `$env:PATH = "$env:USERPROFILE\.deno\bin;$env:PATH";`
3. **`--remote-components ejs:github`**：让 yt-dlp 从 GitHub 下载 JS challenge solver 脚本（首次下载后缓存到本地，后续自动复用）。
4. **手动导出 cookies（备用方案）**：若不使用 Firefox，可使用 Chrome/Edge 配合 `Get cookies.txt LOCALLY` 扩展导出 `www.youtube.com_cookies.txt`，用 `--cookies` 指定。但此文件因 token 轮换容易在几小时内失效。

> B 站不受此限制，仍用原来的 UA + Referer 方式。

---

## 基本用法

### 下载音频（用于转录）

```powershell
# B 站：公开视频无需 cookies，加 UA + Referer 即可
yt-dlp --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36" --referer "https://www.bilibili.com" -f "ba" -o "文件名.%(ext)s" "视频URL"

# YouTube：使用 Firefox cookies + remote-components（推荐）
$env:PATH = "$env:USERPROFILE\.deno\bin;$env:PATH"; yt-dlp --cookies-from-browser firefox --remote-components ejs:github -f "ba" -o "文件名.%(ext)s" "YouTube链接"
```

### 下载视频（需要 cookies 获取高清）

```powershell
# 使用 Firefox cookies 下载 1080P 视频（B 站）
yt-dlp --cookies-from-browser firefox -f "bestvideo[height<=1080]+bestaudio" -o "文件名.%(ext)s" "B站链接"

# 查看可用格式
yt-dlp --cookies-from-browser firefox --list-formats "视频URL"
```

### 下载字幕

```powershell
# 列出可用字幕（YouTube）
$env:PATH = "$env:USERPROFILE\.deno\bin;$env:PATH"; yt-dlp --cookies-from-browser firefox --remote-components ejs:github --list-subs "YouTube链接"

# 下载自动生成的字幕（--write-auto-sub）
$env:PATH = "$env:USERPROFILE\.deno\bin;$env:PATH"; yt-dlp --cookies-from-browser firefox --remote-components ejs:github --write-auto-sub --sub-lang en-orig --sub-format srt --skip-download -o "文件名.%(ext)s" "YouTube链接"

# 下载人工上传的字幕（--write-sub）
yt-dlp --write-sub --sub-lang zh-Hans -o "文件名.%(ext)s" "视频URL"
```

### 批量下载（B 站分 P 视频）

```powershell
# 下载全部分 P 的音频
yt-dlp --user-agent "Mozilla/5.0 ..." --referer "https://www.bilibili.com" -f "ba" -o "BV号_P%(playlist_index)s.%(ext)s" "视频URL"

# 下载指定分 P（如 P3 到 P7）
yt-dlp ... --playlist-items 3-7 "视频URL"
```

---

## Cookies 说明

### 为什么需要 cookies

| 场景 | 需要 cookies？ |
|------|---------------|
| B 站公开视频的音频 / 480P 视频 | ❌ 加 UA + Referer 就够 |
| B 站 720P / 1080P 视频 | ✅ 需要登录态 |
| B 站 1080P 高码率 / 4K | ✅ 需要大会员 |
| YouTube 普通视频 | ❌ 通常不需要 |
| YouTube 年龄限制视频 | ✅ 需要登录态 |

### cookies 来源与使用

推荐使用 **Firefox 自动读取** 方案作为主力，因为它不需要手动维护文件，由浏览器自动更新。

| 方案 | 参数写法 | 适用场景 / 说明 |
| :--- | :--- | :--- |
| **Firefox 自动读取（推荐）** | `--cookies-from-browser firefox` | **YouTube + B站通用**。只需在 Firefox 登录一次账号即可。yt-dlp 会读取其 SQLite 数据库，伴随网页刷新自动轮换 token。 |
| **手动导出文件（备用）** | `--cookies "D:\Antigravity-Hub\工具脚本\yt-dlp\cookies_edge.txt"` | 适用于没有装 Firefox 时的备用。需通过 Edge 扩展 `Get cookies.txt LOCALLY` 导出（约 6 个月过期）。 |

#### 为什么 Chrome/Edge 无法自动读取？
Chrome 127+ 和对应版本的 Edge 引入了 App-Bound Encryption（应用绑定加密），导致 yt-dlp 的 `--cookies-from-browser chrome/edge` 在 Windows 上永久失效（[yt-dlp#10927](https://github.com/yt-dlp/yt-dlp/issues/10927)）。外部程序由于没有应用证书，无法解密其 cookies 数据库。

而 Firefox 目前仍使用传统的 SQLite 存储，未加平台绑定加密，因此是当前唯一的自动读取途径。

> ⚠️ **注意**：运行 yt-dlp 时如果报错提示 cookies 数据库锁死，请尝试先关闭 Firefox 浏览器再执行命令。


---

## B 站下载注意事项

1. **412 错误**：裸请求 B 站会返回 HTTP 412，必须加 `--user-agent` 和 `--referer` 两个 HTTP 头
2. **`--user-agent`**：伪装成浏览器，让 B 站认为是正常访问
3. **`--referer`**：告诉服务器请求来自 bilibili.com，B 站要求此头才返回音视频资源
4. **格式选择**：B 站的视频和音频是分开的流，yt-dlp 下载后会自动用 ffmpeg 合并

---

## 文件输出约定

| 类型 | 存放位置 |
|------|---------|
| 待转录音频 | `Hub\temp\语音转录\audio\` |
| 下载的字幕 | `Hub\temp\语音转录\output\` |
| 其他视频下载 | 按需存放 |

---

## 本目录文件

```
yt-dlp/
├── README.md                      ← 本文件（使用指南）
├── cookies_edge.txt               ← Edge 全量 cookies（B 站等，约 6 月更新一次）
├── cookies_chrome.txt             ← Chrome 全量 cookies（LinuxDo 等，如有需要）
├── www.youtube.com_cookies.txt    ← YouTube 单站 cookies（反爬要求，单独导出）
└── yt-dlp_official_README.md      ← yt-dlp 官方文档（参考用）
```
