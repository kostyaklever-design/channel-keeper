#!/usr/bin/env bash
# Channel Keeper on your own server (Debian / Ubuntu) as a system service.
# Run from the unpacked folder:  sudo bash install.sh
# Run again to update: the code is replaced, the token and the bot's memory stay.
set -euo pipefail

APP=/opt/channel-keeper
DATA=/var/lib/channel-keeper
ENV_FILE=/etc/channel-keeper.env
SERVICE=channel-keeper

if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo: sudo bash install.sh"; exit 1; fi
if [ ! -f bot/main.py ]; then echo "Run it from the Channel Keeper folder (where bot/ is)."; exit 1; fi

echo "1/5 Python"
apt-get update -qq && apt-get install -y -qq python3 python3-venv >/dev/null

echo "2/5 User and folders"
id -u keeper >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin keeper
mkdir -p "$APP" "$DATA"
chown keeper "$DATA" && chmod 700 "$DATA"

echo "3/5 Code"
rm -rf "$APP/bot"
cp -r bot requirements.txt VERSION keeper.yaml posts.yaml sources.yaml "$APP"/ 2>/dev/null || cp -r bot requirements.txt VERSION "$APP"/
[ -d posts ] && cp -r posts "$APP"/
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"

echo "4/5 Token"
if [ ! -f "$ENV_FILE" ]; then
  read -r -s -p "Bot token from @BotFather (hidden): " TOKEN; echo
  [ -n "$TOKEN" ] || { echo "No token — stopped."; exit 1; }
  umask 077
  printf 'BOT_TOKEN=%s\nDATA_DIR=%s\nCONTENT_DIR=%s\n' "$TOKEN" "$DATA" "$APP" > "$ENV_FILE"
else
  echo "   kept the existing $ENV_FILE"
fi
chmod 600 "$ENV_FILE"

echo "5/5 Service"
cat > /etc/systemd/system/$SERVICE.service <<UNIT
[Unit]
Description=Channel Keeper Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
User=keeper
WorkingDirectory=$APP
EnvironmentFile=$ENV_FILE
ExecStart=$APP/venv/bin/python -m bot.main
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$DATA
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now $SERVICE >/dev/null
systemctl restart $SERVICE

echo
echo "Done. Logs: journalctl -u $SERVICE -f"
echo "Now open the bot in Telegram and send /setup."
