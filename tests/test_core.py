import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/documents"))

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

pdf = load("pdf_pages", "tools/documents/pdf2img.py")
query = load("timestamps", "tools/media/query_timestamp.py")
align = load("alignment", "tools/media/align_qwen.py")
subtitle = load("subtitles", "tools/media/bilibili_json_to_txt.py")
images = load("local_images", "tools/images/localize_md_images.py")

class CoreTests(unittest.TestCase):
    def test_page_selection(self):
        self.assertEqual(pdf.get_all_pages(pdf.parse_pages("3-4,1,3")), [1, 3, 4])
        with self.assertRaises(ValueError):
            pdf.parse_pages("0-2")

    def test_filename_safety(self):
        self.assertEqual(pdf.sanitize_path_component("CON"), "_CON")
        self.assertNotIn(":", pdf.sanitize_path_component("a:b"))

    def test_time_format(self):
        self.assertEqual(query.format_timestamp(3661), "1:01:01")
        self.assertEqual(query.format_timestamp(-2), "00:00")

    def test_query(self):
        index = ROOT / "examples/input/sentences.jsonl"
        result = query.query_index(index, "S00002", 5, 0.45)
        self.assertEqual((result[0][1]["start"], result[0][1]["end"]), (5, 10))
        matched = query.query_index(index, "A useful note points back to the evidence", 1, 0.45)
        self.assertEqual(matched[0][1]["id"], "S00002")

    def test_sentence_boundaries(self):
        self.assertEqual(align.split_short_sentences("先读原件。再看图片！"), ["先读原件。", "再看图片！"])
        self.assertEqual(align.normalize_alignable_text("A，B 1"), "ab1")

    def test_zero_second_subtitle(self):
        data = json.loads((ROOT / "examples/input/subtitles.json").read_text(encoding="utf-8"))
        self.assertEqual(data["body"][0]["from"], 0)
        text = (ROOT / "examples/input/subtitles.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("[00:00]"))

    def test_asset_name(self):
        self.assertEqual(images.get_url_extension("https://example.test/a.jpg?x=1"), ".jpg")
        self.assertEqual(images.generate_filename("https://example.test/diagram.png"), "diagram.png")

if __name__ == "__main__":
    unittest.main()
