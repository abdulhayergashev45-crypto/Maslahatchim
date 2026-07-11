#!/bin/sh
set -e

if [ -z "$TELEGRAM_API_ID" ] || [ -z "$TELEGRAM_API_HASH" ]; then
  echo "XATO: TELEGRAM_API_ID va TELEGRAM_API_HASH muhit o'zgaruvchilari kerak."
  echo "my.telegram.org/apps dan oling va Render'dagi Environment bo'limiga qo'shing."
  exit 1
fi

mkdir -p /data/telegram-bot-api

echo "Local Telegram Bot API server ishga tushmoqda..."
telegram-bot-api \
  --api-id="$TELEGRAM_API_ID" \
  --api-hash="$TELEGRAM_API_HASH" \
  --http-port=8081 \
  --dir=/data/telegram-bot-api \
  --temp-dir=/data/telegram-bot-api/temp \
  --local \
  --max-webhook-connections=0 &

# Server tayyor bo'lguncha kutamiz
echo "Serverning tayyor bo'lishini kutyapmiz..."
for i in $(seq 1 30); do
  if curl -s "http://localhost:8081" > /dev/null 2>&1; then
    echo "Local Bot API server tayyor."
    break
  fi
  sleep 1
done

echo "Python bot ishga tushmoqda..."
exec python bot.py
