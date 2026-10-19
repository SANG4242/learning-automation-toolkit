"""按句子 ID 或文本查询短句级时间戳索引。"""

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def normalize_text(text: str) -> str:
    kept = []
    for char in str(text or ""):
        category = unicodedata.category(char)
        if category.startswith("L") or category.startswith("N"):
            kept.append(char.casefold())
    return "".join(kept)


def format_timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def score_match(query: str, text: str) -> float:
    normalized_query = normalize_text(query)
    normalized_text = normalize_text(text)
    if not normalized_query or not normalized_text:
        return 0.0
    if normalized_query == normalized_text:
        return 1.0
    if normalized_query in normalized_text:
        return 0.98
    if normalized_text in normalized_query:
        return 0.95
    return SequenceMatcher(None, normalized_query, normalized_text).ratio()


def iter_records(path: Path):
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"索引第 {line_number} 行不是有效 JSON：{error}") from error


def query_index(path: Path, query: str, limit: int, threshold: float) -> list[tuple[float, dict]]:
    normalized_id = query.strip().upper()
    id_pattern = re.compile(r"^S\d+$", re.IGNORECASE)
    matches = []
    recent = []

    for record in iter_records(path):
        record_id = str(record.get("id", "")).upper()
        if id_pattern.fullmatch(normalized_id):
            if record_id == normalized_id:
                return [(1.0, record)]
            continue

        recent.append(record)
        recent = recent[-3:]
        for size in range(1, len(recent) + 1):
            group = recent[-size:]
            combined = {
                "id": group[0].get("id", "-") if size == 1 else f"{group[0].get('id', '-')}-{group[-1].get('id', '-')}",
                "text": "".join(str(item.get("text", "")) for item in group),
                "start": group[0].get("start", 0),
                "end": group[-1].get("end", 0),
            }
            score = score_match(query, combined["text"])
            if score >= threshold:
                matches.append((score, combined))

    matches.sort(key=lambda item: (
        -item[0],
        len(normalize_text(item[1].get("text", ""))),
        float(item[1].get("end", 0)) - float(item[1].get("start", 0)),
        float(item[1].get("start", 0)),
    ))
    unique = []
    seen = set()
    for match in matches:
        key = (match[1].get("id"), match[1].get("start"), match[1].get("end"))
        if key not in seen:
            seen.add(key)
            unique.append(match)
        if len(unique) >= limit:
            break
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="查询短句对应的视频时间戳")
    parser.add_argument("index", type=Path, help=".sentences.jsonl 短句索引")
    parser.add_argument("query", help="句子 ID 或原文片段")
    parser.add_argument("--limit", type=int, default=5, help="最多返回几项（默认 5）")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.45,
        help="模糊匹配最低分数（默认 0.45）",
    )
    args = parser.parse_args()

    if not args.index.exists():
        parser.error(f"索引不存在：{args.index}")
    if args.limit <= 0:
        parser.error("--limit 必须大于 0")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold 必须在 0～1 之间")

    matches = query_index(args.index, args.query, args.limit, args.threshold)
    if not matches:
        print("没有找到匹配句子")
        return

    for score, record in matches:
        start = format_timestamp(float(record.get("start", 0)))
        end = format_timestamp(float(record.get("end", 0)))
        print(
            f"{record.get('id', '-')} [{start}-{end}] "
            f"{record.get('text', '')} (匹配 {score:.2f})"
        )


if __name__ == "__main__":
    main()
