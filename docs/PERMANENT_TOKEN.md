# Permanent WhatsApp token (System User)

The token you copy from **WhatsApp > API Setup** in the Meta developer dashboard expires after about 24 hours. When it does, the bot keeps receiving messages but every reply fails with `HTTP 401` (you'll see `whatsapp_send ... mode=failed` in the logs). For anything live, we use a **System User token** that never expires.

You need admin access to the Meta Business portfolio that owns the app and the WhatsApp Business Account (WABA).

## 1. Create the system user

1. Open **Meta Business Settings**: <https://business.facebook.com/settings>, and pick the right business portfolio.
2. Go to **Users > System users** and click **Add**.
3. Name it, for example `cyberfield-whatsapp-bot`, set **System user role** to **Admin**, then click **Create system user**.

## 2. Give it the app and the WhatsApp account

With the new system user selected, click **Assign assets**:

1. **Apps**: tick your WhatsApp app and turn on **Full control** (Manage app). Save.
2. **Assign assets** again, then **WhatsApp accounts**: tick your WhatsApp Business Account and turn on **Full control** (Manage WhatsApp Business Accounts). Save.

The system user's page should now list both assets.

## 3. Generate the token

1. On the system user, click **Generate new token**.
2. **App**: choose your WhatsApp app.
3. **Token expiration**: choose **Never**.
4. **Permissions**: tick both
   - `whatsapp_business_messaging` (send and receive messages)
   - `whatsapp_business_management` (templates, phone numbers, webhook subscriptions)
5. Click **Generate token** and copy it right away. Meta shows it only once.

Put it in `.env` and restart the app:

```env
WHATSAPP_TOKEN=<the system user token>
```

Keep it like a password: never commit it, paste it into chat or put it in a screenshot. If it ever leaks, go back to the system user and click **Revoke tokens**, then generate a new one.

## 4. Subscribe the app to your WABA

Webhooks only reach your app once it's subscribed to the WhatsApp Business Account. Find the **WhatsApp Business Account ID** under **WhatsApp > API Setup** (it's not the phone number ID). Then, in PowerShell or any shell:

```bash
curl -X POST "https://graph.facebook.com/v20.0/<WABA_ID>/subscribed_apps" \
  -H "Authorization: Bearer <WHATSAPP_TOKEN>"
# -> {"success":true}

# check it:
curl "https://graph.facebook.com/v20.0/<WABA_ID>/subscribed_apps" \
  -H "Authorization: Bearer <WHATSAPP_TOKEN>"
```

On Windows PowerShell, use `curl.exe` (not the `curl` alias) and put the whole command on one line:

```powershell
curl.exe -X POST "https://graph.facebook.com/v20.0/<WABA_ID>/subscribed_apps" -H "Authorization: Bearer <WHATSAPP_TOKEN>"
```

## 5. Check it works

```bash
curl "https://graph.facebook.com/v20.0/<PHONE_NUMBER_ID>?fields=display_phone_number,verified_name" \
  -H "Authorization: Bearer <WHATSAPP_TOKEN>"
```

Then send the business number a WhatsApp message. The dashboard should show the chat, and the logs should show `whatsapp_send` with `mode=live`.

## Also set the app secret

Under **App settings > Basic > App secret** in the developer dashboard, copy the app secret into `WHATSAPP_APP_SECRET`. The webhook then rejects any POST that isn't signed by Meta (`X-Hub-Signature-256`).
