#!/usr/bin/env python3
"""
Chinese Bedtime Story Generator

Generates a ~300-character Chinese bedtime story (3 paragraphs) using the Claude API.
Vocabulary is sourced from data/chinese_words.txt.
Story continuity is tracked in state/story_state.json.
Output is saved as an HTML file (Arial 15pt) ready for Google Docs import.

Usage:
    python scripts/generate_story.py [--character NAME] [--keywords KW1,KW2] [--fresh-start true]
"""

import argparse
import html
import json
import os
import re
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
WORDS_FILE  = ROOT / "data" / "chinese_words.txt"
STORIES_DIR = ROOT / "stories"
STATE_FILE  = ROOT / "state" / "story_state.json"

STORIES_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "state").mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_chinese_words() -> list[str]:
    """Load Chinese vocabulary from words file.

    Words may be separated by any combination of newlines, spaces, and commas.
    Lines that begin with # (after stripping) are treated as comments and ignored.
    """
    if not WORDS_FILE.exists():
        raise FileNotFoundError(
            f"Words file not found: {WORDS_FILE}\n"
            "Please add your Chinese vocabulary to data/chinese_words.txt"
        )

    raw = WORDS_FILE.read_text(encoding="utf-8")
    no_comments = "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("#")
    )
    words = [w for w in re.split(r"[\s,]+", no_comments) if w]

    if not words:
        raise ValueError("data/chinese_words.txt is empty. Please add Chinese words.")
    return words


def load_state() -> dict:
    """Load persisted story state from disk."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "character_name": "",
        "story_count": 0,
        "last_story_date": None,
        "last_story_summary": None,
        "last_story_file": None,
    }


def save_state(state: dict) -> None:
    """Persist story state to disk."""
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def unique_filename(story_number: int, today: str) -> Path:
    """Return an .html filename that does not already exist.

    If story_NNN_YYYY-MM-DD.html is taken (two runs on the same day),
    append _2, _3, ... until a free slot is found.
    """
    candidate = STORIES_DIR / f"story_{story_number:03d}_{today}.html"
    counter = 2
    while candidate.exists():
        candidate = STORIES_DIR / f"story_{story_number:03d}_{today}_{counter}.html"
        counter += 1
    return candidate


def build_prompt(
    words: list[str],
    character_name: str,
    keywords: list[str],
    previous_summary: str | None,
    fresh_start: bool,
) -> str:
    """Compose the Claude prompt for story generation."""
    word_sample = random.sample(words, min(15, len(words)))
    word_list   = "、".join(word_sample)

    character_line = (
        f"故事的主角名字叫：{character_name}"
        if character_name
        else "请为故事创造一个可爱的主角"
    )

    keyword_block = ""
    if keywords:
        keyword_block = f"故事主题关键词（请围绕以下主题展开）：{'、'.join(keywords)}\n"

    continuation_block = ""
    if previous_summary and not fresh_start:
        continuation_block = (
            f"这个故事是上周故事的续集，请自然地衔接上周的情节。\n"
            f"上周故事摘要：\n{previous_summary}\n"
        )

    return f"""请为3-6岁小朋友创作一个中文睡前故事，严格遵守以下要求：

1. 故事长度：正文分三段，每段约100个汉字，合计约300个汉字
2. {character_line}
3. 只有一个主角，故事温馨、有教育意义，语言简单易懂，适合睡前阅读
4. 三段正文要有起承转合，构成完整的故事弧度（开局→发展→结尾）
5. 请在故事正文中自然地使用下列词语中的至少5个：{word_list}
{keyword_block}{continuation_block}
请严格按照以下格式输出，不要添加其他内容：

【故事标题】
（标题写在这里）

【故事正文】
（第一段：开局，约100字）

（第二段：发展，约100字）

（第三段：结尾，约100字）

【故事摘要】
（用2-3句话概括本周故事情节，供下周续写参考）
"""


def parse_response(text: str) -> tuple[str, str, str]:
    """Extract title, story body, and summary from Claude's response."""
    title = story = summary = ""
    for section in text.split("【"):
        if section.startswith("故事标题】"):
            title   = section[len("故事标题】"):].strip()
        elif section.startswith("故事正文】"):
            story   = section[len("故事正文】"):].strip()
        elif section.startswith("故事摘要】"):
            summary = section[len("故事摘要】"):].strip()
    if not story:
        story   = text.strip()
        title   = "睡前故事"
        summary = story[:80]
    return title, story, summary


def story_to_html(
    title: str,
    story: str,
    today: str,
    character: str,
    keywords: list[str],
    story_number: int,
    prev_file: str | None,
) -> str:
    """Render story data as an HTML document styled Arial 15pt for Google Docs."""
    # Split story into paragraphs on blank lines; skip empty chunks
    paragraphs_html = "\n".join(
        f"<p>{html.escape(para.strip())}</p>"
        for para in re.split(r"\n{2,}", story)
        if para.strip()
    )

    keyword_str = html.escape(", ".join(keywords) if keywords else "无")
    prev_str    = html.escape(prev_file or "（全新故事）")
    title_esc   = html.escape(title)
    char_esc    = html.escape(character)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <title>{title_esc}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      font-size: 15pt;
      max-width: 820px;
      margin: 48px auto;
      line-height: 2;
      color: #111;
    }}
    h1 {{
      font-family: Arial, sans-serif;
      font-size: 18pt;
      margin-bottom: 16px;
    }}
    table {{
      border-collapse: collapse;
      margin-bottom: 28px;
      font-size: 12pt;
    }}
    td, th {{
      border: 1px solid #ccc;
      padding: 5px 14px;
      text-align: left;
    }}
    th {{
      background-color: #f2f2f2;
    }}
    hr {{
      border: none;
      border-top: 1px solid #ddd;
      margin: 28px 0;
    }}
    p {{
      margin: 0 0 1.2em 0;
      text-indent: 2em;
    }}
  </style>
</head>
<body>
  <h1>{title_esc}</h1>
  <table>
    <tr><th>字段</th><th>内容</th></tr>
    <tr><td>日期</td><td>{html.escape(today)}</td></tr>
    <tr><td>主角</td><td>{char_esc}</td></tr>
    <tr><td>关键词</td><td>{keyword_str}</td></tr>
    <tr><td>故事编号</td><td>第 {story_number} 期</td></tr>
    <tr><td>续集自</td><td>{prev_str}</td></tr>
  </table>
  <hr>
{paragraphs_html}
</body>
</html>
"""


# ── Main pipeline ─────────────────────────────────────────────────────────────

def generate_story(character_name: str, keywords: list[str], fresh_start: bool) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    words  = load_chinese_words()
    state  = load_state()

    if fresh_start:
        state["last_story_summary"] = None
        state["story_count"]        = 0
        print("Fresh start: previous story continuity cleared.")

    resolved_character = character_name or state.get("character_name") or "小鲸鱼"
    state["character_name"] = resolved_character

    story_number = state["story_count"] + 1
    print(f"Generating story #{story_number}")
    print(f"  Character : {resolved_character}")
    print(f"  Keywords  : {keywords or '(none)'}")
    print(f"  Fresh start: {fresh_start}")
    print(f"  Continuing from: {state.get('last_story_summary', '(none)') or '(none)'}")

    prompt = build_prompt(
        words=words,
        character_name=resolved_character,
        keywords=keywords,
        previous_summary=state.get("last_story_summary"),
        fresh_start=fresh_start,
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text
    title, story, summary = parse_response(response_text)

    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = unique_filename(story_number, today)

    story_html = story_to_html(
        title=title,
        story=story,
        today=today,
        character=resolved_character,
        keywords=keywords,
        story_number=story_number,
        prev_file=state.get("last_story_file"),
    )
    filename.write_text(story_html, encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"标题: {title}")
    print(f"{'='*50}")
    print(story)
    print(f"{'='*50}")
    print(f"摘要: {summary}")
    print(f"{'='*50}")
    print(f"\nStory saved to: {filename}")

    state["story_count"]        = story_number
    state["last_story_date"]    = today
    state["last_story_summary"] = summary
    state["last_story_file"]    = filename.name
    save_state(state)
    print("State updated. Next week's story will continue from this one.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chinese Bedtime Story Generator — powered by Claude API"
    )
    parser.add_argument("--character", default="",
        help="Main character name (e.g. 小明). Persisted across weeks if set.")
    parser.add_argument("--keywords", default="",
        help="Comma-separated story theme keywords (e.g. '旅行,节日').")
    parser.add_argument("--fresh-start", default="false",
        help="Pass 'true' to ignore previous story and start fresh.")
    args = parser.parse_args()

    keywords    = [k.strip() for k in args.keywords.split(",") if k.strip()]
    fresh_start = str(args.fresh_start).lower() in ("true", "1", "yes")

    generate_story(
        character_name=args.character.strip(),
        keywords=keywords,
        fresh_start=fresh_start,
    )


if __name__ == "__main__":
    main()
