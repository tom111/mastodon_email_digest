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

- [ ] Language filtering (`--language`) — for users who follow people writing in
      multiple languages.

- [ ] CI workflow (`update.yml:30`) uses `SimpleWeighted` scorer, but the CLI
      default and Makefile use `FriendWeighted` (the better scorer). Should be
      consistent.

- [ ] The affinity window for `FriendWeightedScorer` is hardcoded to 7 days
      (`api.py:82`). Could be a CLI option.

## To think through

- [ ] How to handle time zones and activity windows. The old overnight section
      split posts by age (older than N hours), but this is a poor proxy for
      "posts the user missed while sleeping". Better approaches might include:
      letting the user specify their active hours / timezone, or simply relying
      on the lookback window (`-n`) and scoring to surface what matters regardless
      of when it was posted.
