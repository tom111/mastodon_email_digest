# TODO

## Bugs

- [ ] `scorers.py:37` — `InverseFollowerWeight` returns 0.0 for accounts with zero
      followers, completely suppressing them. Should return 1.0 (or a small fallback)
      so new/small accounts aren't silently invisible.

- [ ] `formatters.py:36`, `run.py:173` — `%-d` in strftime is Linux-only and fails
      on macOS/Windows. Use `datetime.day` directly instead.

## Design / Features

- [ ] Show `network_boost_count` in the digest email — it's tracked per post but
      never displayed. Telling the reader "3 of your follows boosted this" is
      useful signal.

- [ ] Add a `--min-score` / minimum engagement floor so posts with a single fav
      can't appear in the digest just because everyone else scored 0.

- [ ] Language filtering (`--language`) — for users who follow people writing in
      multiple languages.

- [ ] The overnight section threshold is hardcoded to LAX (`run.py:136`) regardless
      of the `--threshold` flag. Could expose as `--overnight-threshold`.

- [ ] CI workflow (`update.yml:30`) uses `SimpleWeighted` scorer, but the CLI
      default and Makefile use `FriendWeighted` (the better scorer). Should be
      consistent.

- [ ] The affinity window for `FriendWeightedScorer` is hardcoded to 7 days
      (`api.py:82`). Could be a CLI option.
