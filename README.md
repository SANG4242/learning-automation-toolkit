# Learning Automation Toolkit

[简体中文](README.zh-CN.md) · [Project](https://sang4242.pages.dev/en/projects/course-automation/) · [Context system](https://sang4242.pages.dev/en/projects/agent-context/)

This is the collection of tools and conventions I used throughout my second year of university. It grew from slide rendering and contact sheets into recording retrieval, transcription, classroom overviews, time alignment, selected frames and illustrated Markdown notes. Through a semester of regular use and adjustment, the components became reasonably stable in my own environment.

The design goes beyond scripts: **layered navigation makes resources discoverable, course context keeps the state, task plugins organize work, full specifications define the output, and AI decides what to inspect and how to explain it.**

## A complete, real course example

[Algorithm Design and Analysis: the divide-and-conquer class of 2 April 2026](examples/algorithm-divide-conquer/README.en.md) includes the full chain:

| Material | Read it |
| --- | --- |
| Complete ASR transcript | [Classroom transcript](examples/algorithm-divide-conquer/ASR转录/算法设计与分析_2026-04-02_qwen_vllm.md) |
| Overview and slide mapping | [Class overview](examples/algorithm-divide-conquer/.agent/asr概述/2026-04-02_Ch5.md) |
| Complete slides | [Chapter 5 and prerequisite Chapters 3/4](examples/algorithm-divide-conquer/课件/) |
| Chapter notes and 27 illustrations | [Full divide-and-conquer notes](examples/algorithm-divide-conquer/笔记/ch5_分治法.md) |
| Course context | [Material entry](examples/algorithm-divide-conquer/.agent/memory.md) and [original course rules](examples/algorithm-divide-conquer/.agent/context/原课程上下文.md) |

![Slide P7 used by the actual chapter notes](examples/algorithm-divide-conquer/笔记/ch5_分治法.assets/ch5_P7.jpg)

The teaching materials and classroom transcript are shared with permission **solely to demonstrate the complete workflow and its results**. Their original authors/instructor retain their rights; see the case introduction. These are the actual full documents, not a newly generated miniature example.

## Architecture

```text
Hub entry: route a task to materials, conventions and tools
  ├─ Calling guide → tool README → scripts / models / external programs
  └─ Course .agent/memory.md: resources, rules and installed plugins
       ├─ progress.md: current state and next steps
       ├─ completed_tasks_log.md: completed work and questions
       ├─ plugins/: task-specific installed workflows
       └─ slides, ASR transcript, overview, notes and images
```

- **Layered reading:** establish the map, then follow only relevant entries. Parameters stay with tools; course details stay with courses.
- **Three-file context:** stable information, current state and completed history have separate homes, so a new conversation can continue.
- **Plugins:** install course explanation or ASR workflows when needed, load them on their declared triggers, and retain course-specific rules when updating them.
- **AI plus tools:** scripts execute rendering, retrieval, transcription and frame extraction. AI checks readability, selects visuals, verifies terminology and structures the notes.

Read the [full architecture](docs/architecture.md), browse the [Hub entry](hub/.agent/memory.md), or see the [installed-plugin course example](examples/plugin-course/README.md). The original specifications, tool guides and course documents are in Chinese; this README provides an English entry to them.

## Full specifications and plugins

| Document | Purpose |
| --- | --- |
| [Context types and plugin registry](standards/上下文规范/.agent/memory.md) | Selection, installation and upgrades |
| [General project specification](standards/上下文规范/通用项目/通用项目上下文规范.md) | Software, tools and delivery projects |
| [Course-learning specification](standards/上下文规范/课程学习/课程学习上下文规范.md) | Theory courses, chapter study and questions |
| [Course-task specification](standards/上下文规范/课程任务/课程任务上下文规范.md) | Reports, assignments and presentations |
| [Course explanation plugin](standards/上下文规范/课程学习/插件/课程讲解与答疑.md) | Material selection and teaching pace |
| [ASR organization plugin](standards/上下文规范/课程学习/插件/ASR录播整理.md) | Transcripts, overviews, emphasis and slide mapping |
| [Slide-note specification](standards/笔记整理规范/PPT课件笔记整理规范.md) | Prerequisites, explanation, page references and figures |
| [Video-note specification](standards/笔记整理规范/视频图文笔记整理规范.md) | Narrative, time anchors and visual explanation |
| [Video-processing workflow](standards/笔记整理规范/视频图文笔记处理流程.md) | Retrieval, transcription, alignment and frame selection |

These are the full source documents and templates, not replacements condensed into short workflows. Add a task plugin by defining its prerequisites, trigger, inputs, steps, output and write-back locations; copy it into the project's `.agent/plugins/` and register it in the entry. Shared updates do not automatically overwrite a project's installed rules. See the [specification index](standards/README.md).

## Tools and original manuals

| Module | Included capabilities | Documentation |
| --- | --- | --- |
| Retrieval | Look recordings/slides, length checks, resume/retry; yt-dlp media and subtitles | [Retrieval guide](tools/acquisition/README.md) |
| Course tools | Shared CLI, YourTJ, timetable export/query, Look | [Tools and complete READMEs](tools/course-tools/README.md) |
| Documents | Office→PDF→page images, WPS/Office/LibreOffice, batches, cache, pages and contact sheets | [Document tools](tools/documents/README.md) |
| Images | Grids, selection, labels, ImageMagick recipes and Markdown image localization | [Image tools](tools/images/README.md) |
| Speech and time | Concurrent vLLM requests, low-energy chunking, VAD, WSL auto-start/idle release, direct Qwen/Whisper fallbacks, alignment and lookup | [Full speech guide and original .agent entry](tools/media/README.md) |
| MinerU | Local GPU wrapper, API batches, polling, caches, Markdown and .assets organization | [Both routes and original manuals](tools/mineru/README.md) |

The original Hub guides for [documents](hub/guides/工具-文档.md), [media](hub/guides/工具-音视频.md) and [course tools](hub/guides/工具-课程.md) are included. The [public command map](hub/README.md) relates the original machine layout to this repository. Canvas remains a separate CLI/MCP project composed with these tools.

## Get started

Choose the modules you need. The base image tools use Python 3.10+ and Pillow. PDF rendering needs ImageMagick and Ghostscript; media processing needs FFmpeg. Install Office engines and GPU environments according to the relevant tool README.

```powershell
git clone https://github.com/SANG4242/learning-automation-toolkit.git
cd learning-automation-toolkit
python -m pip install -r requirements.txt
python tools/documents/pdf2img.py slides.pdf --output .local/pages
```

Create context for your course, install the task plugins, and give the AI the course entry, source locations and intended output. For example: “Follow the course entry and installed plugins to prepare this class's ASR overview, then write illustrated notes using the full slide specification.” It follows the indexes, chooses inputs, runs tools, inspects the results and updates the course records.

ASR entry:

```powershell
python -m pip install -r requirements/asr-client.txt
$env:LEARNING_AUDIO_DIR = 'C:/study/audio'
$env:QWEN_ASR_MODEL = 'Qwen/Qwen3-ASR-1.7B'
python -u tools/media/transcribe_qwen_vllm.py --file lesson.mp4
```

See the [speech README](tools/media/README.md) for WSL services, models, alignment, fallbacks and configuration. Intermediates default to `.local/`, configurable with `LEARNING_TOOLS_DATA_DIR`. Supply your own authentication and install model weights separately.

## Use and feedback

The toolkit comes from sustained personal study and has primarily been used on my own machine. The GitHub version separates personal paths, configuration and credentials, so it differs from my daily local setup. If you encounter a problem, please [open an Issue](https://github.com/SANG4242/learning-automation-toolkit/issues); I will do my best to help investigate and resolve it.

A [small authored slide demo](examples/slide-notes.md) and [video-location demo](examples/video-notes.md) remain available for a quick try, alongside the full real course case.

## License and sources

The repository's own scripts, specifications and authored demos are [MIT](LICENSE). Teaching material and classroom content in the real case are included only for the stated demonstration purpose. Models, engines, APIs and third-party documents retain their own terms. See [sources and original-document notes](docs/sources.md).
