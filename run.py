from __future__ import annotations

import argparse
import inspect
import logging
import os
import random
import smtplib
import sys
from collections import defaultdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from mastodon import Mastodon

from api import fetch_affinity_accounts, fetch_list_accounts, fetch_posts_and_boosts, fetch_trending_posts
from formatters import format_posts
from scorers import get_scorers
from thresholds import get_threshold_from_name, get_thresholds

if TYPE_CHECKING:
    from scorers import Scorer
    from thresholds import Threshold as ThresholdType


def render_digest(context: dict, output_dir: Path) -> str:
    """Renders the digest template and writes index.html. Returns the HTML string."""
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("digest.html.jinja")
    output_html = template.render(context)
    output_file_path = output_dir / "index.html"
    output_file_path.write_text(output_html)
    logging.info("Digest written to %s", output_file_path)
    return output_html


def send_email(html_body: str, subject: str) -> None:
    """Sends the digest as an HTML email using SMTP credentials from the environment."""
    mail_server = os.environ["MAIL_SERVER"]
    mail_port = int(os.environ.get("MAIL_SERVER_PORT", "465"))
    mail_username = os.environ["MAIL_USERNAME"]
    mail_password = os.environ["MAIL_PASSWORD"]
    mail_from = os.environ.get("MAIL_FROM", mail_username)
    mail_destination = os.environ["MAIL_DESTINATION"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_destination
    msg.attach(MIMEText(html_body, "html"))

    logging.info("Sending digest email to %s via %s:%s", mail_destination, mail_server, mail_port)
    if mail_port == 465:
        with smtplib.SMTP_SSL(mail_server, mail_port) as smtp:
            smtp.login(mail_username, mail_password)
            smtp.sendmail(mail_from, mail_destination, msg.as_string())
    else:
        with smtplib.SMTP(mail_server, mail_port) as smtp:
            smtp.starttls()
            smtp.login(mail_username, mail_password)
            smtp.sendmail(mail_from, mail_destination, msg.as_string())
    logging.info("Email sent successfully")


def _make_scorer(scorer_class, affinity_accounts: set[str], list_accounts: set[str]):
    """Instantiates a scorer, passing social context if the class accepts it."""
    sig = inspect.signature(scorer_class.__init__)
    params = sig.parameters
    if "affinity_accounts" in params:
        return scorer_class(
            affinity_accounts=affinity_accounts,
            list_accounts=list_accounts,
        )
    return scorer_class()


def _cap_per_account(posts: list, scorer, max_per_account: int) -> list:
    """Keep only the top `max_per_account` posts per account, ranked by score."""
    by_account: dict[str, list] = defaultdict(list)
    for p in posts:
        acct_id = str(p.info["account"]["id"])
        by_account[acct_id].append(p)
    result = []
    for acct_id, acct_posts in by_account.items():
        acct_posts.sort(key=lambda p: p.get_score(scorer), reverse=True)
        result.extend(acct_posts[:max_per_account])
    return result


def _pick_serendipity(
    boosts: list,
    posts: list,
    affinity_accounts: set[str],
    mastodon_client,
    count: int = 3,
) -> list:
    """Pick serendipity posts: boosts from unfamiliar accounts, with trending fallback."""
    # Accounts that posted directly to the timeline are followed
    followed_ids = {str(p.info["account"]["id"]) for p in posts}
    familiar_ids = followed_ids | affinity_accounts

    # Candidates: boosts from accounts the user doesn't follow or interact with
    candidates = [
        b for b in boosts
        if str(b.info["account"]["id"]) not in familiar_ids
    ]

    # Deduplicate by account — at most one per account for variety
    seen_accounts: set[str] = set()
    unique_candidates = []
    for c in candidates:
        acct_id = str(c.info["account"]["id"])
        if acct_id not in seen_accounts:
            seen_accounts.add(acct_id)
            unique_candidates.append(c)

    if len(unique_candidates) >= count:
        return random.sample(unique_candidates, count)

    # Fallback: trending posts, excluding followed/familiar accounts
    picks = list(unique_candidates)
    remaining = count - len(picks)
    picked_ids = {str(p.info["account"]["id"]) for p in picks}

    trending = fetch_trending_posts(mastodon_client, limit=20)
    trending_candidates = [
        t for t in trending
        if str(t.info["account"]["id"]) not in familiar_ids | picked_ids
    ]
    # Deduplicate by account
    for t in trending_candidates:
        acct_id = str(t.info["account"]["id"])
        if acct_id not in picked_ids and remaining > 0:
            picks.append(t)
            picked_ids.add(acct_id)
            remaining -= 1

    return picks


def run(
    hours: int,
    scorer_class,
    threshold: ThresholdType,
    mastodon_token: str,
    mastodon_base_url: str,
    mastodon_username: str,
    output_dir: Path,
    no_email: bool = False,
    exclude_lists: bool = False,
    languages: list[str] | None = None,
    language_penalty: float = 0.5,
    min_score: float = 0,
    affinity_days: int = 7,
    max_per_account: int = 3,
    max_posts: int = 20,
) -> None:

    logging.info("Building digest from the past %d hours...", hours)

    mst = Mastodon(
        access_token=mastodon_token,
        api_base_url=mastodon_base_url,
    )

    # Fetch social context for scorers that use it, or for --exclude-lists
    affinity_accounts: set[str] = set()
    list_accounts: set[str] = set()
    sig = inspect.signature(scorer_class.__init__)
    needs_social_context = "affinity_accounts" in sig.parameters
    if needs_social_context or exclude_lists:
        logging.info("Fetching social context (favourites + lists)...")
        if needs_social_context:
            affinity_accounts = fetch_affinity_accounts(mst, days=affinity_days)
        list_accounts = fetch_list_accounts(mst)
        logging.info(
            "Social context: %d affinity accounts, %d list accounts",
            len(affinity_accounts),
            len(list_accounts),
        )

    scorer = _make_scorer(scorer_class, affinity_accounts, list_accounts)

    # Fetch all posts and boosts from the home timeline
    posts, boosts = fetch_posts_and_boosts(hours, mst, mastodon_username)
    logging.info("Fetched %d posts and %d boosts", len(posts), len(boosts))

    # Exclude posts from list members (user already reads these in a list client)
    if exclude_lists and list_accounts:
        posts = [p for p in posts if str(p.info["account"]["id"]) not in list_accounts]
        boosts = [p for p in boosts if str(p.info["account"]["id"]) not in list_accounts]
        logging.info("After excluding list accounts: %d posts and %d boosts", len(posts), len(boosts))

    # Apply language penalty to non-preferred languages (before scoring)
    if languages:
        lang_set = {lang.lower() for lang in languages}
        for p in posts + boosts:
            post_lang = (p.info.get("language") or "").lower()
            if post_lang and post_lang not in lang_set:
                p.score_multiplier *= language_penalty

    # Score and filter by percentile
    filtered_posts = threshold.posts_meeting_criteria(posts, scorer)
    filtered_boosts = threshold.posts_meeting_criteria(boosts, scorer)

    # Apply minimum score floor
    if min_score > 0:
        filtered_posts = [p for p in filtered_posts if p.get_score(scorer) >= min_score]
        filtered_boosts = [p for p in filtered_boosts if p.get_score(scorer) >= min_score]

    # Cap posts per account to avoid a single voice dominating the digest
    if max_per_account > 0:
        filtered_posts = _cap_per_account(filtered_posts, scorer, max_per_account)
        filtered_boosts = _cap_per_account(filtered_boosts, scorer, max_per_account)

    # Hard cap: keep only the top N by score if we exceed max_posts
    if max_posts > 0:
        if len(filtered_posts) > max_posts:
            filtered_posts.sort(key=lambda p: p.get_score(scorer), reverse=True)
            filtered_posts = filtered_posts[:max_posts]
        if len(filtered_boosts) > max_posts:
            filtered_boosts.sort(key=lambda p: p.get_score(scorer), reverse=True)
            filtered_boosts = filtered_boosts[:max_posts]

    # Pick serendipity posts from the full (unfiltered) boosts pool
    serendipity = _pick_serendipity(boosts, posts, affinity_accounts, mst)
    logging.info("Serendipity: %d posts selected", len(serendipity))

    threshold_posts = format_posts(filtered_posts, mastodon_base_url)
    serendipity_posts = format_posts(serendipity, mastodon_base_url)
    threshold_boosts = format_posts(filtered_boosts, mastodon_base_url)

    logging.info(
        "After filtering: %d posts, %d serendipity, %d boosts",
        len(threshold_posts),
        len(serendipity_posts),
        len(threshold_boosts),
    )

    # Render
    html = render_digest(
        context={
            "hours": hours,
            "posts": threshold_posts,
            "serendipity": serendipity_posts,
            "boosts": threshold_boosts,
            "mastodon_base_url": mastodon_base_url,
            "rendered_at": datetime.now(timezone.utc).isoformat(),
            "threshold": threshold.get_name(),
            "scorer": scorer.get_name(),
        },
        output_dir=output_dir,
    )

    if no_email:
        logging.info("--no-email set; skipping email send")
        return

    required_mail_vars = ["MAIL_SERVER", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_DESTINATION"]
    missing = [v for v in required_mail_vars if not os.environ.get(v)]
    if missing:
        logging.warning("Missing mail env vars: %s — skipping email", ", ".join(missing))
        return

    now = datetime.now(timezone.utc)
    subject = f"Mastodon Digest — {now.strftime('%b')} {now.day}, {now.year}"
    send_email(html, subject)


if __name__ == "__main__":
    load_dotenv()

    scorers = get_scorers()
    thresholds = get_thresholds()

    arg_parser = argparse.ArgumentParser(
        prog="mastodon_digest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    arg_parser.add_argument(
        "-n",
        choices=range(1, 25),
        default=12,
        dest="hours",
        help="The number of hours to include in the Mastodon Digest",
        type=int,
    )
    arg_parser.add_argument(
        "-s",
        choices=list(scorers.keys()),
        default="FriendWeighted",
        dest="scorer",
        help=(
            "Which post scoring criteria to use. "
            "Simple scorers use geometric mean of boosts and favs. "
            "Extended scorers add reply counts. "
            "Weighted scorers penalise large accounts. "
            "FriendBoost uses network boost count. "
            "FriendWeighted adds affinity and list membership boosts."
        ),
    )
    arg_parser.add_argument(
        "-t",
        choices=list(thresholds.keys()),
        default="normal",
        dest="threshold",
        help="lax=90th pct, normal=95th pct, strict=98th pct",
    )
    arg_parser.add_argument(
        "-o",
        default="./render/",
        dest="output_dir",
        help="Output directory for the rendered digest",
    )
    arg_parser.add_argument(
        "--languages",
        default=None,
        dest="languages",
        help="Comma-separated ISO 639-1 language codes (e.g. en,de,nl). Posts in other languages are penalized, not excluded. Posts with no language tag are treated as preferred.",
    )
    arg_parser.add_argument(
        "--language-penalty",
        default=0.5,
        dest="language_penalty",
        help="Score multiplier for posts in non-preferred languages (0.0–1.0, default 0.5)",
        type=float,
    )
    arg_parser.add_argument(
        "--exclude-lists",
        action="store_true",
        default=False,
        dest="exclude_lists",
        help="Exclude posts from accounts on your Mastodon lists (useful if you already read lists in a separate client)",
    )
    arg_parser.add_argument(
        "--min-score",
        default=0,
        dest="min_score",
        help="Minimum absolute score for a post to appear in the digest (0 = disabled)",
        type=float,
    )
    arg_parser.add_argument(
        "--affinity-days",
        default=7,
        dest="affinity_days",
        help="How many days of favourites to consider for the affinity bonus (FriendWeighted scorer)",
        type=int,
    )
    arg_parser.add_argument(
        "--max-posts",
        default=20,
        dest="max_posts",
        help="Maximum posts (and boosts) in the digest; on busy days only the top N by score are kept (0 = unlimited)",
        type=int,
    )
    arg_parser.add_argument(
        "--max-per-account",
        default=3,
        dest="max_per_account",
        help="Maximum posts per account in the digest (0 = unlimited)",
        type=int,
    )
    arg_parser.add_argument(
        "--no-email",
        action="store_true",
        default=False,
        dest="no_email",
        help="Skip sending email; just write render/index.html",
    )
    arg_parser.add_argument(
        "--log-file",
        default=None,
        dest="log_file",
        help="Path to log file (in addition to stdout)",
    )
    args = arg_parser.parse_args()

    # Configure logging
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )

    output_dir = Path(args.output_dir)
    if not output_dir.exists() or not output_dir.is_dir():
        sys.exit(f"Output directory not found: {args.output_dir}")

    mastodon_token = os.getenv("MASTODON_TOKEN")
    mastodon_base_url = os.getenv("MASTODON_BASE_URL", "").rstrip("/")
    if mastodon_base_url and not mastodon_base_url.startswith(("http://", "https://")):
        mastodon_base_url = "https://" + mastodon_base_url
    mastodon_username = os.getenv("MASTODON_USERNAME", "").lstrip("@")

    if not mastodon_token:
        sys.exit("Missing environment variable: MASTODON_TOKEN")
    if not mastodon_base_url:
        sys.exit("Missing environment variable: MASTODON_BASE_URL")
    if not mastodon_username:
        sys.exit("Missing environment variable: MASTODON_USERNAME")

    run(
        hours=args.hours,
        scorer_class=scorers[args.scorer],
        threshold=get_threshold_from_name(args.threshold),
        mastodon_token=mastodon_token,
        mastodon_base_url=mastodon_base_url,
        mastodon_username=mastodon_username,
        output_dir=output_dir,
        no_email=args.no_email,
        exclude_lists=args.exclude_lists,
        languages=args.languages.split(",") if args.languages else None,
        language_penalty=args.language_penalty,
        min_score=args.min_score,
        affinity_days=args.affinity_days,
        max_per_account=args.max_per_account,
        max_posts=args.max_posts,
    )
