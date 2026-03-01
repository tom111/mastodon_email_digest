from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from models import ScoredPost

if TYPE_CHECKING:
    from mastodon import Mastodon


def fetch_posts_and_boosts(
    hours: int, mastodon_client: Mastodon, mastodon_username: str
) -> tuple[list[ScoredPost], list[ScoredPost]]:
    """Fetches posts from the home timeline that the account hasn't interacted with."""

    TIMELINE_LIMIT = 1000

    start = datetime.now(timezone.utc) - timedelta(hours=hours)

    posts: list[ScoredPost] = []
    boosts: list[ScoredPost] = []
    # Maps post URL -> ScoredPost for dedup and live boost-count updates
    seen_posts: dict[str, ScoredPost] = {}
    url_boost_counts: dict[str, int] = {}
    total_posts_seen = 0

    response = mastodon_client.timeline(min_id=start)
    while response and total_posts_seen < TIMELINE_LIMIT:

        for timeline_entry in response:
            total_posts_seen += 1

            # Skip posts the server already marked as hidden by a filter (Mastodon.py 2.x)
            filter_results = timeline_entry.get("filtered", [])
            if any(
                fr.get("filter", {}).get("filter_action") == "hide"
                for fr in filter_results
            ):
                continue

            is_boost = timeline_entry["reblog"] is not None
            actual_post = timeline_entry["reblog"] if is_boost else timeline_entry

            post_url = actual_post.get("url") or actual_post.get("uri", "")
            if not post_url:
                continue

            if is_boost:
                url_boost_counts[post_url] = url_boost_counts.get(post_url, 0) + 1
                # If already added, update its network boost count
                if post_url in seen_posts:
                    seen_posts[post_url].network_boost_count = url_boost_counts[post_url]
                    continue

            if post_url not in seen_posts:
                scored_post = ScoredPost(actual_post)
                scored_post.network_boost_count = url_boost_counts.get(post_url, 0)

                # Skip posts the user has already interacted with or authored
                if (
                    not scored_post.info["reblogged"]
                    and not scored_post.info["favourited"]
                    and not scored_post.info["bookmarked"]
                    and scored_post.info["account"]["acct"] != mastodon_username
                ):
                    if is_boost:
                        boosts.append(scored_post)
                    else:
                        posts.append(scored_post)
                    seen_posts[post_url] = scored_post

        # fetch_next() follows the `next` Link header → older posts within our window
        response = mastodon_client.fetch_next(response)

    return posts, boosts


def fetch_affinity_accounts(mastodon_client: Mastodon, days: int = 7) -> set[str]:
    """Returns account IDs of users whose posts the current user has recently favourited."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        account_ids: set[str] = set()
        response = mastodon_client.favourites()
        while response:
            for fav in response:
                if fav["created_at"] < cutoff:
                    return account_ids
                account_ids.add(str(fav["account"]["id"]))
            response = mastodon_client.fetch_next(response)
        return account_ids
    except Exception as exc:
        logging.warning("Could not fetch affinity accounts: %s", exc)
        return set()


def fetch_list_accounts(mastodon_client: Mastodon) -> set[str]:
    """Returns account IDs of all members of the user's lists."""
    try:
        account_ids: set[str] = set()
        lists = mastodon_client.lists()
        for lst in lists:
            accounts = mastodon_client.list_accounts(lst["id"])
            while accounts:
                for acct in accounts:
                    account_ids.add(str(acct["id"]))
                accounts = mastodon_client.fetch_next(accounts)
        return account_ids
    except Exception as exc:
        logging.warning("Could not fetch list accounts: %s", exc)
        return set()
