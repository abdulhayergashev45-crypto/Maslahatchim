# ---- 1-bosqich: tayyor Telegram Bot API server binarysini olish ----
FROM aiogram/telegram-bot-api:latest AS tbaserver

# ---- 2-bosqich: asosiy Python muhiti ----
FROM python:3.11-slim

# telegram-bot-api ishga tushishi uchun kerakli kutubxonalar + curl (health-check uchun)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Tayyor binaryni 1-bosqichdan ko'chirib olamiz
COPY --from=tbaserver /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

CMD ["./start.sh"]
