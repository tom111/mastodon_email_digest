from html import escape


def format_post(post, mastodon_base_url) -> dict:

    def format_media(media):
        media_type = media["type"]
        url = escape(media["url"], quote=True)
        if media_type == "image":
            alt = escape(media["description"] or "", quote=True)
            return f'<div class="media"><img src="{url}" alt="{alt}"></div>'
        elif media_type in ("video", "gifv"):
            return f'<a href="{url}" class="placeholder" title="see the video on mastodon">🎞️</a>'
        return ""

    def format_displayname(display_name, emojis):
        display_name = escape(display_name)
        for emoji in emojis:
            shortcode = escape(emoji["shortcode"], quote=True)
            url = escape(emoji["url"], quote=True)
            display_name = display_name.replace(
                f":{emoji['shortcode']}:",
                f'<img alt="{shortcode}" src="{url}">',
            )
        return display_name

    account_avatar = post.info["account"]["avatar"]
    account_url = post.info["account"]["url"]
    display_name = format_displayname(
        post.info["account"]["display_name"],
        post.info["account"]["emojis"],
    )
    username = post.info["account"]["username"]
    content = post.info["content"]
    media = "\n".join([format_media(m) for m in post.info["media_attachments"]])
    dt = post.info["created_at"]
    created_at = f"{dt.strftime('%b')} {dt.day}, {dt.year} at {dt.strftime('%H:%M')}"
    home_url = post.get_home_url(mastodon_base_url)
    original_url = post.info["url"]
    replies_count = post.info["replies_count"]
    reblogs_count = post.info["reblogs_count"]
    favourites_count = post.info["favourites_count"]

    return dict(
        account_avatar=account_avatar,
        account_url=account_url,
        display_name=display_name,
        username=username,
        content=content,
        media=media,
        created_at=created_at,
        home_url=home_url,
        original_url=original_url,
        replies_count=replies_count,
        reblogs_count=reblogs_count,
        favourites_count=favourites_count,
    )


def format_posts(posts, mastodon_base_url):
    return [format_post(post, mastodon_base_url) for post in posts]
