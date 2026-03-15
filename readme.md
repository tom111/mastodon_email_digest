# Mastodon Email Digest

A daily email digest of the best posts from your Mastodon home timeline.

## Why

Social media algorithms are designed to maximize engagement, not to inform you.
Reverse-chronological feeds are better, but on a busy timeline you still miss
good posts while drowning in noise. This project takes a middle path: it scores
posts by engagement signals, filters to the top percentile, and emails you a
short digest once a day. You stay informed without doomscrolling.

## How it works

1. **Fetch** your home timeline (up to 1000 posts in the lookback window)
2. **Score** each post using a geometric mean of boosts, favourites, and replies
3. **Filter** to the top percentile (configurable: 90th / 95th / 98th)
4. **Cap** the digest to avoid overload (per-account limit + total limit)
5. **Serendipity** section: 3 posts from accounts you don't follow, surfaced
   through your network's boosts (falls back to instance trending posts)
6. **Render** as HTML and email it to you

## Quick start

```bash
cp .env.example .env   # fill in your Mastodon + SMTP credentials
pip install -r requirements.txt
mkdir -p render
python run.py -n 24 -s FriendWeighted -t lax --no-email
open render/index.html
```

See [deploy.md](deploy.md) for full deployment instructions (cron, systemd, Docker).

## CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `-n` | `12` | Hours to look back (1-24) |
| `-s` | `FriendWeighted` | Scorer algorithm |
| `-t` | `normal` | Threshold: `lax` (90th), `normal` (95th), `strict` (98th) |
| `-o` | `./render/` | Output directory |
| `--languages` | all | Comma-separated ISO 639-1 codes (e.g. `en,de`) |
| `--language-penalty` | `0.5` | Score multiplier for non-preferred languages |
| `--exclude-lists` | off | Drop posts from accounts on your Mastodon lists |
| `--min-score` | `0` | Minimum absolute score (0 = disabled) |
| `--affinity-days` | `7` | Days of favourites for affinity scoring |
| `--max-posts` | `20` | Max posts per section (0 = unlimited) |
| `--max-per-account` | `3` | Max posts per account (0 = unlimited) |
| `--no-email` | off | Write HTML only, don't send email |
| `--log-file` | none | Log to file in addition to stdout |

## Scorers

- **Simple** / **SimpleWeighted** -- geometric mean of boosts and favourites
- **ExtendedSimple** / **ExtendedSimpleWeighted** -- adds reply count
- **FriendBoost** -- weighs network boost count (how many of your follows boosted it)
- **FriendWeighted** -- adds affinity bonus (accounts you recently favourited) and list membership bonus

`Weighted` variants divide by sqrt(follower count) to prevent large accounts from dominating.

## History

Originally forked from [hodgesmr/mastodon_digest](https://github.com/hodgesmr/mastodon_digest)
via [mauforonda/mastodon_digest](https://github.com/mauforonda/mastodon_digest).
This fork has diverged significantly with new scoring algorithms, email delivery,
language filtering, serendipity posts, and digest size controls.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
