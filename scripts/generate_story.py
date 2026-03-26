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
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
WORDS_FILE  = ROOT / "data" / "chinese_words.txt"
STORIES_DIR = ROOT / "stories"
STATE_FILE  = ROOT / "state" / "story_state.json"

STORIES_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "state").mkdir(parents=True, exist_ok=True)

# Basic Chinese function/grammar words that are always permitted and do not
# count against the vocabulary restriction.
GRAMMAR_WORDS = (
    "的、地、得、了、着、过、是、在、有、和、也、就、都、还、很、不、没、这、那、一"
    "、他、她、她、它、上、下、里、来、去、说、看、想、走、跑、飞、叫、笑、哭"
    "、大、小、多、少、好、坟、新、旧、长、短、高、低、把、被、对、向、从、用、让、就"
    "、才、又、只、最、非常、可以、要、会、能、于是、然后、因为、所以、虽然、但是、如果、就是"
)


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
    """Compose the Claude prompt with strict vocabulary restrictions."""
    full_word_list = "、".join(words)

    character_line = (
        f"主角名字：「{character_name}」（允许直接使用）"
        if character_name
        else "请从词汇表中选一个词作为主角名字"
    )

    keyword_line = ""
    if keywords:
        keyword_line = f"主题关键词：「{'、'.join(keywords)}」（允许直接使用）\n"

    continuation_block = ""
    if previous_summary and not fresh_start:
        continuation_block = (
            f"本故事是上周故事的续集，请自然衔接上周情节。\n"
            f"上周摘要：{previous_summary}\n"
        )

    return f"""任务：为3-6岁小朋友创作一个中文睡前故事。

═════ 《词汇限制——必须严格执行》 ═════

故事正文中的所有内容词（名词、动词、形容词、副词）必须且只能来自以下三个来源：

来源1——词汇表（共{len(words)}个词）：
{full_word_list}

来源2——固定允许词：
{character_line}
{keyword_line}
来源3——补充词（最多3个）：
你可自行选择最多3个词汇表以外的词，使故事更流畅。尔后必须在《新增词语》中列出它们。

下列基础虚词和语法词可自由使用，不占用上述配额：
{GRAMMAR_WORDS}

═════ 故事要求 ═════

1. 正文分三段（开局→发展→结尾），每段约100字，合计约300字
2. 只有一个主角，故事温馨有教育意义，语言简单，适合睡前阅读
3. 严格遵守上方词汇限制
{continuation_block}
═════ 输出格式（不得添加其他内容） ═════

【故事标题】
（标题）

【故事正文】
（第一段：开局，约100字）

（第二段：发展，约100字）

（第三段：结尾，约100字）

【新增词语】
（列出你额外使用的最多3个词，用逗号分隔。若未增加任何新词请填写“无”）

【故事摘要】
（用2-3句概括本周情节，供下周续写参考）
"""


def parse_response(text: str) -> tuple[str, str, str, str]:
    """Extract title, story body, new words, and summary from Claude's response."""
    title = story = new_words = summary = ""
    for section in text.split("【"):
        if section.startswith("故事标题】"):
            title     = section[len("故事标题】"):].strip()
        elif section.startswith("故事正文】"):
            story     = section[len("故事正文】"):].strip()
        elif section.startswith("新增词语】"):
            new_words = section[len("新增词语】"):].strip()
        elif section.startswith("故事摘要】"):
            summary   = section[len("故事摘要】"):].strip()
    if not story:
        story     = text.strip()
        title     = "睡前故事"
        new_words = ""
        summary   = story[:80]
    return title, story, new_words, summary


def story_to_html(
    title: str,
    story: str,
    new_words: str,
    today: str,
    character: str,
    keywords: list[str],
    story_number: int,
    prev_file: str | None,
) -> str:
    """Render story data as an HTML document styled Arial 15pt for Google Docs."""
    paragraphs_html = "\n".join(
        f"  <p>{html.escape(para.strip())}</p>"
        for para in re.split(r"\n{2,}", story)
        if para.strip()
    )

    keyword_str  = html.escape(", ".join(keywords) if keywords else "无")
    prev_str     = html.escape(prev_file or "（全新故事）")
    title_esc    = html.escape(title)
    char_esc     = html.escape(character)
    new_words_esc = html.escape(new_words if new_words and new_words != "无" else "无")

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
    <tr><td>新增词语</td><td>{new_words_esc}</td></tr>
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
    print(f"  Vocabulary: {len(words)} words loaded from {WORDS_FILE.name}")
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
    title, story, new_words, summary = parse_response(response_text)

    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = unique_filename(story_number, today)

    story_html = story_to_html(
        title=title,
        story=story,
        new_words=new_words,
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
    print(f"新增词语: {new_words or '无'}")
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
