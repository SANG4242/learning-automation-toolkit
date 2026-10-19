"""Build self-authored slides and a silent, manually timed video example."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
INPUT = HERE / "input"
SLIDES = [
    ("1. Make the source readable", "Keep diagrams, formulas and page layout.", ["Source document", "Page images", "Overview + close reading"]),
    ("2. Keep a source anchor", "A useful note points back to the evidence.", ["Claim in the note", "Source page or timestamp", "Selected visual + explanation"]),
    ("3. Review the output", "Check what tools cannot decide on their own.", ["Terminology and conditions", "Image readability", "Coverage and missing context"]),
]

def font(size):
    for candidate in ("DejaVuSans.ttf", "Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)

def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)

def main():
    INPUT.mkdir(parents=True, exist_ok=True)
    pages = []
    for index, (title, subtitle, labels) in enumerate(SLIDES, start=1):
        image = Image.new("RGB", (1200, 800), "#f7f9fc")
        draw = ImageDraw.Draw(image)
        draw.text((60, 52), "LEARNING WORKFLOW / SELF-AUTHORED EXAMPLE", font=font(22), fill="#526479")
        draw.text((60, 120), title, font=font(39), fill="#15304f")
        draw.text((60, 194), subtitle, font=font(26), fill="#40546c")
        for position, label in enumerate(labels):
            y = 290 + position * 125
            draw.rounded_rectangle((60, y, 1140, y + 94), 16, fill="white", outline="#cbd7e4", width=2)
            draw.text((90, y + 25), label, font=font(28), fill="#1c5b85")
        draw.text((60, 744), f"Page {index} / 3 · Zhi Sang", font=font(20), fill="#526479")
        image.save(INPUT / f"slide-{index}.png")
        pages.append(image)
    pages[0].save(INPUT / "slides.pdf", save_all=True, append_images=pages[1:], resolution=120)
    for page in pages:
        page.close()
    run(sys.executable, ROOT / "tools/documents/pdf2img.py", INPUT / "slides.pdf", "--output", ROOT / ".local/demo", "--names", "pages")
    run(sys.executable, ROOT / "tools/images/image_stitcher.py", "-i", ROOT / ".local/demo/pages", "--preset", "4", "--auto-size", "-o", HERE / "preview", "-p", "slides-overview")
    assets = HERE / "slide-notes.assets"
    assets.mkdir(exist_ok=True)
    shutil.copy2(ROOT / ".local/demo/pages/2.jpg", assets / "page-2-source-anchor.jpg")
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "1/5", "-start_number", "1", "-i", INPUT / "slide-%d.png", "-t", "15", "-c:v", "libx264", "-vf", "fps=25,format=yuv420p", INPUT / "silent-workflow.mp4")
    sentences = [{"id": f"S{i:05d}", "text": slide[1], "start": (i-1)*5, "end": i*5} for i, slide in enumerate(SLIDES, 1)]
    (INPUT / "sentences.jsonl").write_text("".join(json.dumps(row) + "\n" for row in sentences), encoding="utf-8")
    subtitles = [{"from": row["start"], "to": row["end"], "content": row["text"]} for row in sentences]
    (INPUT / "subtitles.json").write_text(json.dumps({"body": subtitles}, indent=2), encoding="utf-8")
    run(sys.executable, ROOT / "tools/media/bilibili_json_to_txt.py", INPUT / "subtitles.json", "-o", INPUT / "subtitles.md")
    run(sys.executable, ROOT / "tools/media/query_timestamp.py", INPUT / "sentences.jsonl", "S00002")
    video_assets = HERE / "video-notes.assets"
    video_assets.mkdir(exist_ok=True)
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "6", "-i", INPUT / "silent-workflow.mp4", "-frames:v", "1", video_assets / "source-anchor-at-00m06.jpg")
    print("Demo built. Video timestamps are authored, not ASR/aligner output.")

if __name__ == "__main__":
    main()
