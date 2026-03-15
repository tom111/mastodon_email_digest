# TODO

## Bugs

- [x] `scorers.py:37` — `InverseFollowerWeight` returns 0.0 for accounts with zero
      followers, completely suppressing them. Should return 1.0 (or a small fallback)
      so new/small accounts aren't silently invisible.

- [x] `formatters.py:36`, `run.py:173` — `%-d` in strftime is Linux-only and fails
      on macOS/Windows. Use `datetime.day` directly instead.

## Design / Features

- [x] Show `network_boost_count` in the digest email — it's tracked per post but
      never displayed. Telling the reader "3 of your follows boosted this" is
      useful signal.

- [x] Add a `--min-score` / minimum engagement floor so posts with a single fav
      can't appear in the digest just because everyone else scored 0.

- [x] Add `--exclude-lists` flag to drop posts from accounts on your lists
      (for users who already read lists in a dedicated client like Ivory).

- [x] Language filtering (`--languages`, `--language-penalty`) — posts in non-preferred
      languages are penalized rather than excluded.

- [x] CI workflow (`update.yml:29`) uses `SimpleWeighted` scorer, but the CLI
      default and Makefile use `FriendWeighted` (the better scorer). Now consistent.

- [x] The affinity window for `FriendWeightedScorer` is hardcoded to 7 days
      (`api.py:82`). Now configurable via `--affinity-days`.

- [x] Per-account cap — no single account appears more than N times (default 3).
      Configurable via `--max-per-account`.

- [x] Digest size cap (`--max-posts`, default 20) — on busy days, keeps only the
      top N posts/boosts by score. Quiet days naturally produce fewer posts via the
      percentile threshold.

- [x] Serendipity section — 3 posts from unfamiliar accounts (not followed, not in
      affinity set), picked randomly from the boosts pool. Falls back to instance
      trending posts if not enough candidates. Shown between Posts and Boosts.

- [ ] Update the README file.  This is now a new fork with new perspective.

## To think through

- [ ] How to handle time zones and activity windows. The old overnight section
      split posts by age (older than N hours), but this is a poor proxy for
      "posts the user missed while sleeping". Better approaches might include:
      letting the user specify their active hours / timezone, or simply relying
      on the lookback window (`-n`) and scoring to surface what matters regardless
      of when it was posted.

- [ ] Stop running this on Microsoft github, check different deployment methods.