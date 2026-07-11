# ---- 1-bosqich: tayyor Telegram Bot API server binarysini olish (Alpine asosida) ----
FROM aiogram/telegram-bot-api:latest AS tbaserver

# ---- 2-bosqich: asosiy Python muhiti — ENDI HAM ALPINE (mos kelishi uchun) ----
FROM python:3.11-alpine

# Build va runtime uchun kerakli paketlar
RUN apk add --no-cache \
    ffmpeg \
    font-dejavu \
    curl \
    ca-certificates \
    gcc \
    musl-dev \
    libffi-dev \
    python3-dev

# Tayyor binaryni 1-bosqichdan ko'chirib olamiz (endi ikkalasi ham Alpine/musl)
COPY --from=tbaserver /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

CMD ["./start.sh"]
