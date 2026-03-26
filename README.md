# babywhale_story

Automated pipeline that generates Chinese bedtime stories using the Claude API,
driven by a custom vocabulary list you provide.

---

## One-time Setup

### 1. Enable GitHub Actions

1. Go to your repository on GitHub.
2. Click the **Actions** tab at the top of the page.
3. If prompted with _"Workflows aren't being run on this forked repository"_, click **I understand my workflows, go ahead and enable them**.
4. The workflow **Chinese Bedtime Story Pipeline** will now appear in the left sidebar under Actions.

### 2. Add your Anthropic API key

1. Go to **Settings** (repo top bar) → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
3. Name: `ANTHROPIC_API_KEY` | Value: your key from [console.anthropic.com](https://console.anthropic.com).
4. Click **Add secret**.

### 3. Add your Chinese vocabulary

Edit `data/chinese_words.txt`. Words can be separated by **newlines, spaces, or commas** — any mix works:

```
# Style 1 — one word per line
小鲸鱼
大海
月亮

# Style 2 — space-separated
星星 妈妈 爸爸 朋友

# Style 3 — comma-separated
快乐,勇敢,善良,帮助
```

Lines starting with `#` are ignored. The pipeline randomly samples 15 words each run.

---

## Running the Pipeline

1. Go to **Actions** → **Chinese Bedtime Story Pipeline** (left sidebar).
2. Click **Run workflow** (top-right of the workflow table).
3. Fill in the parameters and click the green **Run workflow** button.

### Parameters

| Parameter | Description | Example |
|---|---|---|
| `character_name` | Main character’s name. Saved and reused each week once set. | `小明` |
| `keywords` | Comma-separated story themes for this run. | `旅行,节日` |
| `fresh_start` | `true` — drop story continuity and start a brand-new arc. | `true` / `false` |

Leave `character_name` and `keywords` blank to reuse what was saved from the previous run.

---

## How It Works

1. `data/chinese_words.txt` is loaded and 15 words are randomly sampled.
2. The Claude API generates a ~100-character bedtime story that:
   - Features the named main character.
   - Weaves in at least 5 of the sampled words.
   - Follows the theme keywords (if provided).
   - Continues from last week’s story (unless `fresh_start` is `true`).
3. The story is saved as `stories/story_NNN_YYYY-MM-DD.md`.
4. A short summary is written to `state/story_state.json` so next week’s story can continue seamlessly.

---

## File Structure

```
babywhale_story/
├── .github/
│   └── workflows/
│       └── story_pipeline.yml   # GitHub Actions workflow (manual trigger)
├── data/
│   └── chinese_words.txt        # Your Chinese vocabulary list
├── scripts/
│   ├── generate_story.py        # Story generation script (Claude API)
├──   └── requirements.txt         # Python dependencies (anthropic)
├── stories/                     # Generated story Markdown files
└── state/
    └── story_state.json         # Auto-generated: tracks continuity
```

---

## Image Generation

Claude does not natively generate images. To add images, extend
`scripts/generate_story.py` after the story save step to call an image API
(e.g. DALL-E, Stable Diffusion) and store the result alongside the Markdown file.
Add the image API key as an additional repository secret.
