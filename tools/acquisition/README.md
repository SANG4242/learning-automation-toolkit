# 材料获取：录播、字幕和课程平台

## 本地录播与课件

[课程工具统一入口](../course-tools/README.md)保留Look录播／课件、YourTJ课程和排课、课表导出及查询脚本。录播下载保留长度检查、断点续传、失败重试和批量日期，输出可直接供ASR使用。

```powershell
python tools/course-tools/course_tools.py look search 算法
python tools/course-tools/course_tools.py look info 课程ID
python tools/course-tools/course_tools.py look download 课程ID 日期
python tools/course-tools/course_tools.py look ppt 课程ID
```

联网获取课程资源使用自己的登录与访问权限，不分发账号、Cookie或下载缓存。

## yt-dlp

[完整原调用说明](yt-dlp/README.md)保留视频、音频、字幕、格式、代理、Cookie和平台处理方法。`yt-dlp`本身由上游提供，这里提供使用说明而不重分发安装包。

```powershell
yt-dlp --write-subs --write-auto-subs --sub-langs 'zh.*,en.*' --skip-download '视频URL'
yt-dlp -o '.local/media/%(title)s.%(ext)s' '视频URL'
```

平台需要登录时使用自己的浏览器会话；字幕与本地ASR相互对照，原始视频供抽帧。完整视频图文流程见[原规范](../../standards/笔记整理规范/视频图文笔记处理流程.md)。

## Canvas课程助手

Canvas课程助手是独立项目，提供CLI/MCP查询课程、作业、截止时间、反馈和资料下载。它由Hub课程指引调用，与这里的文档／ASR工具组合使用，而不是把账号和整个服务复制到工具链中。

当前公开调用说明见[Hub课程指南](../../hub/guides/工具-课程.md)。先查询取得课程和资源ID，再读取详情或下载；课程助手源码的公开入口由其独立项目维护。

## 输入和输出衔接

下载视频或音频 → `LEARNING_AUDIO_DIR` → ASR任务目录 → 正式课程 `ASR转录/`。下载课件 → 课程 `课件/` → 页图或本地解析。课程入口登记正式资料，中间分块、对齐和候选帧放任务目录。
