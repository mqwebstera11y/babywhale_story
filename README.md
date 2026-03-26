# babywhale_story

Automated pipeline that generates weekly Chinese bedtime stories using the Claude API,
built around a custom vocabulary list you provide.

## How It Works

1. **Schedule**: The GitHub Actions workflow runs every workday at 6 PM EST.
   Stories are generated once a week (every Monday by the scheduled trigger).
2. **Vocabulary**: Add Chinese words to `data/chinese_words.txt` (one per line).
   The pipeline randomly samples 15 words each run and weaves them into the story.
3. **Continuity**: Each week's story continues from the previous one.
   The story state (character, summary, count) is saved in `state/story_state.json`.
4. **Output**: Stories are saved as Markdown files in the `stories/` directory,
   named `story_NNN_YYYY-MM-DD.md`.

## Setup

### 1. Add your Anthropic API key

Go to **Settings → Secrets and variables → Actions** and add:

| Secret name          | Value                      |
|----------------------|----------------------------|
| `ANTHROPIC_API_KEY`  | Your Anthropic API key     |

### 2. Add your Chinese vocabulary

Edit `data/chinese_words.txt` and replace the sample words with your own list.
One word per line; lines starting with `#` are treated as comments.

## Running the Pipeline

### Automatic (scheduled)
- Runs every workday at 6 PM EST via GitHub Actions schedule.
- Story is generated every **Monday**; other days the workflow is a no-op.

### Manual trigger

Go to **Actions → Chinese Bedtime Story Pipeline → Run workflow** and fill in:

| Parameter        | Description                                                        | Example              |
|------------------|--------------------------------------------------------------------|----------------------|
| `character_name` | Main character's name. Persists week-to-week once set.            | `小明`               |
| `keywords`       | Comma-separated theme keywords for this week's story.             | `旅行,节日`          |
| `fresh_start`    | `true` = ignore last week's story and start a brand-new arc.      | `true` / `false`     |
| `force_generate` | `true` = generate a story right now regardless of the day.        | `true`               |

## File Structure

```
babywhale_story/
├── .github/
│   └── workflows/
│       └── story_pipeline.yml   # GitHub Actions workflow
├── data/
│   └── chinese_words.txt        # Your Chinese vocabulary list
├── scripts/
│   ├── generate_story.py        # Story generation script (Claude API)
│   └── requirements.txt         # Python dependencies
├── stories/                     # Generated story Markdown files
├── state/
│   └── story_state.json         # Auto-generated: tracks continuity
└── README.md
```

## Image Generation

Claude does not natively generate images. If you would like images alongside
stories, you can extend `scripts/generate_story.py` to call an image generation
API (e.g. DALL-E, Stable Diffusion) after the text story is saved.
A placeholder comment is left in the script where this can be added.

## Notes

- EST = UTC−5. If you want the trigger to follow Eastern *Daylight* Time (UTC−4,
  roughly March–November), change the cron in the workflow from `0 23 * * 1-5`
  to `0 22 * * 1-5`.
- The default character name is `小鲸鱼` (Little Whale). Set `character_name`
  on the first manual run to change it permanently.
