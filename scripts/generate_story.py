#!/usr/bin/env python3
"""
Chinese Bedtime Story Generator

Generates a ~100-character Chinese bedtime story using the Claude API.
Vocabulary is sourced from data/chinese_words.txt.
Story continuity is tracked in state/story_state.json.

Usage:
    python scripts/generate_story.py [--character NAME] [--keywords KW1,KW2] [--fresh-start true]
"""

import argparse
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

    # Drop comment lines before splitting so a '#' comment doesn't become a token
    no_comments = "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("#")
    )

    # Split on any mix of whitespace (space, tab, newline) and commas
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

1. 故事长度：恰好约100个汉字（正文部分）
2. {character_line}
3. 只有一个主角，故事温馨、有教育意义，语言简单易懂，适合睡前阅读
4. 请在故事正文中自然地使用下列词语中的至少5个：{word_list}
{keyword_block}{continuation_block}
请严格按照以下格式输出，不要添加其他内容：

【故事标题】
（标题写在这里）

【故事正文】
（约100字的故事写在这里）

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

    # Character name resolution: CLI arg → saved state → default
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
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text
    title, story, summary = parse_response(response_text)

    # ── Save story file ────────────────────────────────────────────────────────
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = STORIES_DIR / f"story_{story_number:03d}_{today}.md"

    story_md = f"""# {title}

| 字段 | 内容 |
|------|------|
| 日期 | {today} |
| 主角 | {resolved_character} |
| 关键词 | {', '.join(keywords) if keywords else '无'} |
| 故事编号 | 第 {story_number} 期 |
| 续集自 | {state.get('last_story_file') or '（全新故事）'} |

---

{story}

---

*本故事由 AI 自动生成，词汇来自中文学习词汇表。*
"""
    filename.write_text(story_md, encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"标题: {title}")
    print(f"{'='*50}")
    print(story)
    print(f"{'='*50}")
    print(f"摘要: {summary}")
    print(f"{'='*50}")
    print(f"\nStory saved to: {filename}")

    # ── Update state ───────────────────────────────────────────────────────────
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
    parser.add_argument(
        "--character",
        default="",
        help="Main character name (e.g. 小明). Persisted across weeks if set.",
    )
    parser.add_argument(
        "--keywords",
        default="",
        help="Comma-separated story theme keywords (e.g. '旅行,节日').",
    )
    parser.add_argument(
        "--fresh-start",
        default="false",
        help="Pass 'true' to ignore previous story and start fresh.",
    )
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
