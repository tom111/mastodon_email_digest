# Scoring Algorithms

This document describes how posts are scored and filtered for the digest.

## Overview

Every post fetched from your home timeline receives a numeric **score**. Posts are then ranked by percentile and only those above a chosen **threshold** make it into the digest. The score is computed by a **scorer** (the algorithm) and optionally adjusted by a **weight** (to level the playing field between large and small accounts).

## Building Blocks

### Geometric Mean

All scorers use a geometric mean of engagement metrics as their base signal. The geometric mean balances the metrics against each other — a post needs broad engagement, not just one inflated number. Each metric has 1 added before the calculation so that a zero in one metric doesn't collapse the entire score to zero.

For example, a post with 10 reblogs and 40 favourites scores `gmean(11, 41) ≈ 21.2`, while a post with 50 reblogs and 0 favourites scores `gmean(51, 1) ≈ 7.1`. Balanced engagement wins.

### Weighting

Scorers use one of two weighting strategies:

- **Uniform (weight = 1.0):** No adjustment. A post from someone with 100,000 followers is treated the same as one from someone with 50 followers. Large accounts dominate because their raw engagement numbers are naturally higher.

- **Inverse Follower (weight = 1 / sqrt(followers)):** De-emphasises large accounts. The score is divided by the square root of the author's follower count. A post from a 10,000-follower account is penalised 100× relative to a 1-follower account. This surfaces quality posts from smaller accounts that would otherwise be drowned out. Accounts with zero followers are treated as having one follower.

## Scorers

### Simple (`-s Simple`)

The baseline. Computes the geometric mean of reblogs and favourites with uniform weight.

```
score = gmean(reblogs + 1, favourites + 1)
```

**Good for:** A straightforward popularity ranking. Large accounts with high engagement will dominate.

### SimpleWeighted (`-s SimpleWeighted`)

Same formula as Simple, but applies inverse-follower weighting.

```
score = gmean(reblogs + 1, favourites + 1) / sqrt(followers)
```

**Good for:** Surfacing posts from smaller accounts alongside popular ones.

### ExtendedSimple (`-s ExtendedSimple`)

Adds reply count as a third input to the geometric mean, with uniform weight.

```
score = gmean(reblogs + 1, favourites + 1, replies + 1)
```

**Good for:** Rewarding posts that spark conversation, not just passive engagement.

### ExtendedSimpleWeighted (`-s ExtendedSimpleWeighted`)

ExtendedSimple with inverse-follower weighting.

```
score = gmean(reblogs + 1, favourites + 1, replies + 1) / sqrt(followers)
```

**Good for:** Combining conversation-awareness with small-account boosting.

### FriendBoost (`-s FriendBoost`)

Uses your **social network** as the primary signal. Instead of global reblogs, it counts how many people *you follow* boosted a post (`network_boost_count`). If none of your follows boosted it, it falls back to global reblogs. Always applies inverse-follower weighting.

Additionally applies a **controversy penalty**: when a post's replies outnumber its combined favourites and reblogs, the score is dampened. The penalty strength is controlled by `controversy_penalty` (default 0.5, where 0 = no penalty, 1 = full penalty).

```
effective_reblogs = network_boost_count if > 0, else global reblogs
score = gmean(effective_reblogs + 1, favourites + 1) / sqrt(followers)

if replies > (favourites + reblogs):
    ratio = (favourites + reblogs) / replies
    score *= 1.0 - controversy_penalty * (1.0 - ratio)
```

**Good for:** Trusting your own network's taste over raw global numbers. The controversy penalty helps filter out rage-bait and pile-ons.

### FriendWeighted (`-s FriendWeighted`)

Extends FriendBoost with a **social-affinity multiplier**. Two bonus signals are layered on top:

- **Affinity bonus (1.5×):** If you have favourited posts from an account in the last 7 days, their posts get a 1.5× boost. This rewards accounts you actively engage with.

- **List bonus (1.3×):** If the author is in any of your Mastodon lists, their posts get a 1.3× boost. Lists are typically curated for quality, so this is a trust signal.

Both bonuses stack multiplicatively (an account you've recently favourited AND that is in a list gets 1.5 × 1.3 = 1.95×).

```
score = FriendBoost_score
if recently_favourited: score *= 1.5
if in_a_list:           score *= 1.3
```

**Good for:** The most personalised ranking. Combines network trust, recent interaction history, and list curation. This is the default scorer.

## Pre-filters

### Exclude Lists (`--exclude-lists`)

If you already follow your Mastodon lists in a dedicated client (e.g. Ivory), those posts don't need to appear in the digest. When `--exclude-lists` is enabled, all posts from accounts that belong to any of your lists are dropped **before scoring**. This focuses the digest on posts you're likely to miss rather than ones you've already seen.

This works with any scorer, not just FriendWeighted. When combined with FriendWeighted, the list accounts are still fetched (for both exclusion and the affinity multiplier on non-list accounts), so there's no extra API cost.

### Language Penalty (`--languages`, `--language-penalty`)

If you follow people who post in multiple languages, you can specify your preferred languages with `--languages en,de`. Posts in other languages receive a score penalty (default 0.5×, configurable via `--language-penalty`). This means a Dutch or French post needs roughly twice the engagement to appear alongside English/German posts — but a genuinely great post in any language will still make the cut.

Posts with **no language tag** (the `language` field is null or empty) are treated as preferred — no penalty is applied. This is the safe default since many clients don't set the language field.

The penalty is applied as a multiplier on the post's score **before percentile filtering**, so non-preferred language posts compete at a disadvantage rather than being excluded outright.

Language codes are [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) two-letter codes — the same ones Mastodon uses. Common examples: `en` (English), `de` (German), `nl` (Dutch), `fr` (French), `es` (Spanish), `ja` (Japanese), `pt` (Portuguese).

### Minimum Score (`--min-score`)

Sets an absolute score floor applied **after percentile filtering**. During quiet periods, the percentile threshold alone may let zero-engagement posts through. A minimum score (e.g. `--min-score 1.5`) ensures only posts with meaningful engagement appear.

## Thresholds

After scoring, posts are filtered by percentile rank. Only posts at or above the threshold percentile are included in the digest.

| Flag | Name   | Percentile | Effect |
|------|--------|------------|--------|
| `-t lax`    | Lax    | 90th | Top 10% — more posts, broader selection |
| `-t normal` | Normal | 95th | Top 5% — balanced (default) |
| `-t strict` | Strict | 98th | Top 2% — only the best, very few posts |

## CLI Knobs Summary

| Flag | What it controls | Values |
|------|-----------------|--------|
| `-s` | Scoring algorithm | `Simple`, `SimpleWeighted`, `ExtendedSimple`, `ExtendedSimpleWeighted`, `FriendBoost`, `FriendWeighted` |
| `-t` | Percentile threshold | `lax` (90), `normal` (95), `strict` (98) |
| `-n` | Hours to look back | 1–24 (default 12) |
| `-o` | Output directory | path (default `./render/`) |
| `--languages` | Preferred languages | comma-separated codes, e.g. `en,de` (default: none = no penalty) |
| `--language-penalty` | Score multiplier for non-preferred languages | 0.0–1.0 (default 0.5) |
| `--min-score` | Minimum absolute score | float (default 0 = disabled) |
| `--exclude-lists` | Drop posts from list members | flag (default off) |
