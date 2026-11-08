# HexTube

HexTube is a video discovery site built around **542 curated Hacker News videos**, with additional videos discovered from the YouTube channels listed in `channels.txt`. It supports topic filters, search, a daily mix, and watched-state tracking.

## Run locally

    python3 server.py

Then open http://127.0.0.1:8000. Python 3.8+ is sufficient. The app does not need a YouTube API key.

To discover recent uploads from configured channels:

    python3 discover_youtube.py --dry-run
    python3 discover_youtube.py

The script reads `channels.txt` and uses public YouTube channel RSS feeds. It stores new finds in `data/extra_videos.json`. Public RSS feeds expose only a limited number of recent uploads per channel (usually around 15). Add or remove channels in `channels.txt`.

## Cloudflare deployment

The Cloudflare version uses **Workers + static assets + D1**. The original 542 HN videos are imported by the D1 migration. YouTube discovery uses public channel pages and RSS feeds, so **no YouTube Data API key, Google Cloud project, or API secret is required**.

### Deploy

1. Install Node.js LTS, then from this directory run:

       npm install -g wrangler
       wrangler login

2. Create the database:

       wrangler d1 create hextube-db

   Copy the returned `database_id` into `wrangler.toml`, replacing `REPLACE_WITH_D1_DATABASE_ID`.

3. Apply the schema and seed data:

       wrangler d1 migrations apply hextube-db --remote

   This imports the 542 curated HN videos. The migration uses `INSERT OR IGNORE`, so it is safe to re-run.

4. Edit `static/channels.txt` to choose the YouTube channels. Use one channel handle per line, optionally followed by topic labels:

       @AndrejKarpathy | Karpathy, AI & ML, LLMs
       @3blue1brown | Math for ML, AI & ML
       @mCoding | Python

5. Deploy:

       wrangler deploy

   The Worker checks the configured channels on its scheduled run (03:17 UTC daily). YouTube discoveries are inserted without replacing or deleting the existing HN collection. To change the channels, edit `static/channels.txt` and deploy again.

### Discovery notes

- No API key or admin token is needed.
- The Worker resolves each public `@handle` to its channel ID, then reads that channel's public RSS feed.
- Public RSS feeds expose a limited recent-upload window (typically about 15 videos per channel); they are not a complete channel archive.
- There is no keyword-search discovery in this no-key edition. Add channels to `static/channels.txt` instead.
- There is no minimum-view or video-length requirement. The site does not display duration badges or offer a length filter.
- The discovery process still skips obvious off-topic titles and common Shorts/clickbait titles.
- RSS does not provide reliable view counts, duration, or embeddability status. Videos are shown with an ordinary YouTube link/player attempt; if embedding is disabled, use **Open on YouTube**.
- Existing HN videos and previously saved YouTube finds are preserved. Sync is insert-only and deduplicates by video ID and normalized title.

## Files

- `data/curated_list.csv` — curated HN collection for review.
- `data/videos.json` — local curated video data.
- `channels.txt` — local channel configuration.
- `static/channels.txt` — Cloudflare channel configuration.
- `worker.js` — Cloudflare Worker API and scheduled RSS sync.
- `static/index.html` — website frontend.
- `migrations/` — D1 schema and initial HN seed.

## Data and attribution

The original Hacker News collection is based on HackerTube and the open-index/hacker-news archive (ODC-By). YouTube video titles, channel names, and videos belong to their respective creators. HexTube is not affiliated with YouTube, Google, Hacker News, or Y Combinator.
