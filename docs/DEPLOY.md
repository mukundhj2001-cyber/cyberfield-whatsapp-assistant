# Deploying

ngrok on a laptop works for testing, but the bot stops whenever the laptop sleeps, and the ngrok URL changes on every restart. For a client we deploy the same app to a small always-on host. Everything ships as **one Docker container**: the API, the `/webhook` endpoint and the built dashboard.

**The one rule:** SQLite is a single file at `DB_PATH`. It must sit on a **persistent disk or volume**. Otherwise every deploy wipes the orders, chats and settings.

Before you deploy, read [PERMANENT_TOKEN.md](PERMANENT_TOKEN.md). The 24-hour test token won't survive in production.

## Environment

Set these on the host. Every variable is listed in `.env.example`.

| Must set | Why |
|---|---|
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Dashboard login. Without them the login is the public demo `admin / cyberfield` |
| `SESSION_SECRET` | A long random string for signing login cookies |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` | Meta Cloud API |
| `WHATSAPP_APP_SECRET` | Checks that webhook POSTs really come from Meta |
| `DB_PATH=/data/assistant.db` | Points SQLite at the persistent disk (already the default in the Docker image) |

Tip: `python -m app.auth "my-password"` (run inside `backend/`) prints a PBKDF2 hash. You can paste the hash into `ADMIN_PASSWORD` so the plain password never sits on the server.

After deploying, open **Meta developer dashboard > WhatsApp > Configuration > Webhook** and set:
- Callback URL: `https://<your-host>/webhook`
- Verify token: your `WHATSAPP_VERIFY_TOKEN`
- Subscribe to the **messages** field

Only one callback URL can be active at a time. Once production works, ngrok is no longer used.

## Option A: Render (simplest)

1. Push this repo to GitHub (already done).
2. In Render, click **New > Blueprint** and pick the repo. `render.yaml` creates a Docker web service with a 1 GB disk at `/data`. Disks need a paid instance (Starter).
3. Fill in the secret env vars Render asks for, then deploy.
4. Your URL looks like `https://cyberfield-whatsapp-assistant.onrender.com`. Open `/api/health` and check it says `"whatsapp": "live"`.
5. Point the Meta webhook at `https://…onrender.com/webhook`.

Backups: Render takes daily disk snapshots. You can also download the DB from the Render shell with `sqlite3 /data/assistant.db ".backup /data/backup.db"`.

## Option B: Railway

1. **New Project > Deploy from GitHub repo**. Railway finds the `Dockerfile`.
2. On the service, open **Settings > Volumes > Add volume** with mount path `/data`.
3. Under **Variables**, add the env vars above (`DB_PATH=/data/assistant.db`).
4. Under **Settings > Networking > Generate domain**, get the public URL, then point Meta at `https://<domain>/webhook`.

Railway sets `PORT`, and the container listens on it automatically.

## Option C: Any VPS (DigitalOcean, Hetzner, Lightsail, an office machine)

```bash
git clone https://github.com/mukundhj2001-cyber/cyberfield-whatsapp-assistant.git && cd cyberfield-whatsapp-assistant
cp .env.example .env && nano .env        # fill in values
docker build -t cyberfield-wa .
docker run -d --name cyberfield-wa --restart unless-stopped \
  --env-file .env -e DB_PATH=/data/assistant.db -e COOKIE_SECURE=true \
  -v cyberfield-data:/data -p 127.0.0.1:8000:8000 cyberfield-wa
```

Meta needs HTTPS, so put a reverse proxy in front. Caddy gets certificates automatically:

```
# /etc/caddy/Caddyfile
wa.yourdomain.in {
    reverse_proxy 127.0.0.1:8000
}
```

To update: `git pull && docker build -t cyberfield-wa . && docker rm -f cyberfield-wa && <same docker run>`. The `cyberfield-data` volume keeps the DB.
Backup: `docker run --rm -v cyberfield-data:/data -v $PWD:/b alpine cp /data/assistant.db /b/`.

## Logs

Logs are JSON lines on stdout (`LOG_FORMAT=json`, the default; use `LOG_FORMAT=text` locally if you prefer). Each line has an `event`. The useful ones:

| event | meaning |
|---|---|
| `webhook_message` | inbound message accepted |
| `webhook_duplicate_skipped` | Meta re-sent a message we'd already handled (idempotency by message id) |
| `webhook_signature_invalid` | a POST without a valid Meta signature was rejected |
| `whatsapp_send` / `whatsapp_send_retry` | outbound result, with attempts |
| `whatsapp_status` | sent / delivered / read / failed callbacks from Meta |
| `login_failed` | wrong dashboard password |

Tokens and secrets are never logged, and phone numbers are masked to their last 4 digits.

## Scaling note

SQLite with one container comfortably handles a few small businesses. Don't run more than one replica against the same SQLite file. If a client outgrows that, we move to Postgres.
