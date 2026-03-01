# Deployment Checklist

### 1. Set up the directory

- [ ] Clone or copy the repo to `/opt/mastodon_email_digest`
- [ ] `cd /opt/mastodon_email_digest`
- [ ] `python3 -m venv venv`
- [ ] `venv/bin/pip install -r requirements.txt`

### 2. Configure credentials

- [ ] `cp .env.example .env`
- [ ] Edit `.env` and fill in:
  - `MASTODON_TOKEN` — your Mastodon API token
  - `MASTODON_BASE_URL` — e.g. `https://mastodon.social`
  - `MASTODON_USERNAME` — your `user@instance` handle
  - `MAIL_SERVER` — your SMTP server
  - `MAIL_SERVER_PORT` — `465` for SSL, `587` for STARTTLS
  - `MAIL_USERNAME` / `MAIL_PASSWORD`
  - `MAIL_FROM` — display name + address
  - `MAIL_DESTINATION` — where the digest goes
- [ ] `chmod 600 .env` — keep credentials private

### 3. Create the output directory

- [ ] `mkdir -p /opt/mastodon_email_digest/render`

### 4. Test locally (no email)

```bash
cd /opt/mastodon_email_digest
venv/bin/python run.py -n 24 -s FriendWeighted -t lax --no-email
```

- [ ] Confirm `render/index.html` exists and looks right in a browser

### 5. Test email delivery

```bash
venv/bin/python run.py -n 1 -s FriendWeighted -t lax
```

- [ ] Confirm email arrives in your inbox

### 6. Schedule with cron (Gentoo/OpenRC primary)

```bash
INSTALL_DIR=/opt/mastodon_email_digest make install
```

Or manually add to crontab (`crontab -e`):

```
0 16 * * * cd /opt/mastodon_email_digest && /opt/mastodon_email_digest/venv/bin/python run.py -n 24 -s FriendWeighted -t lax --log-file /var/log/mastodon_digest.log >> /var/log/mastodon_digest.log 2>&1
```

- [ ] Run `crontab -l` to verify the entry is there

### 7. (Optional) systemd instead of cron

- [ ] Copy `mastodon-digest.service` and `mastodon-digest.timer` to `/etc/systemd/system/`
- [ ] Edit the `WorkingDirectory` and `ExecStart` paths if your install dir differs
- [ ] `systemctl daemon-reload`
- [ ] `systemctl enable --now mastodon-digest.timer`
- [ ] `systemctl list-timers mastodon-digest.timer` — confirm it's scheduled

### 8. Verify logs

```bash
make logs              # tails ~/mastodon_digest.log
# or
journalctl -u mastodon-digest -f   # if using systemd
```

- [ ] Confirm first scheduled run produces a log entry and an email
