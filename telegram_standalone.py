#!/usr/bin/env python3
"""
Bot Telegram autonome optionnel pour AirQualityInk.
Utilisable si vous souhaitez dédier un bot spécifique à AirQualityInk
(séparé de RaspCam).

Configurez dans .env :
  TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
  TELEGRAM_ALLOWED_CHAT_IDS=12345678,87654321
"""
from __future__ import annotations
import os
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
from raspcam_airq_plugin import is_airq_command, handle_airq_command, handle_photo_upload, cmd_screen

_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_FILE if _ENV_FILE.exists() else None, override=True)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_RAW = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHATS = set(int(cid.strip()) for cid in ALLOWED_RAW.split(",") if cid.strip().isdigit()) if ALLOWED_RAW else None


def send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[Telegram] Erreur envoi message : {e}")


def send_photo(chat_id: int, photo_bytes: bytes, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": ("screenshot.png", photo_bytes, "image/png")}
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data, files=files, timeout=15)
    except Exception as e:
        print(f"[Telegram] Erreur envoi photo : {e}")


def download_file(file_id: str) -> bytes | None:
    try:
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        resp = requests.get(get_file_url, timeout=10).json()
        if not resp.get("ok"):
            return None
        file_path = resp["result"]["file_path"]
        dl_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        dl_resp = requests.get(dl_url, timeout=30)
        if dl_resp.status_code == 200:
            return dl_resp.content
    except Exception as e:
        print(f"[Telegram] Erreur téléchargement fichier : {e}")
    return None


def run_bot():
    if not BOT_TOKEN:
        print("[Telegram Standalone] TELEGRAM_BOT_TOKEN non configuré dans .env. Arrêt.")
        return

    print("[Telegram Standalone] Démarrage du polling Telegram...")
    offset = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=25"
            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                time.sleep(5)
                continue

            data = resp.json()
            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = max(offset, update["update_id"] + 1)
                msg = update.get("message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                if ALLOWED_CHATS and chat_id not in ALLOWED_CHATS:
                    continue

                text = msg.get("text", "").strip()

                # 1. Gestion des photos téléversées
                if "photo" in msg:
                    # Prendre la plus grande résolution (dernière dans la liste)
                    photo_item = msg["photo"][-1]
                    file_id = photo_item["file_id"]
                    send_message(chat_id, "⏳ Réception de l'œuvre en cours...")
                    img_bytes = download_file(file_id)
                    if img_bytes:
                        caption = msg.get("caption")
                        res_msg = handle_photo_upload(img_bytes, filename=caption)
                        send_message(chat_id, res_msg)
                    else:
                        send_message(chat_id, "❌ Échec du téléchargement de la photo.")
                    continue

                # 2. Gestion des commandes
                if text.startswith("/"):
                    if text in ("/start", "/help"):
                        res_text, _ = handle_airq_command("/airq_help")
                        send_message(chat_id, res_text)
                    elif is_airq_command(text):
                        res_text, photo = handle_airq_command(text)
                        if photo:
                            send_photo(chat_id, photo, caption=res_text)
                        else:
                            send_message(chat_id, res_text)

        except Exception as e:
            print(f"[Telegram Standalone] Erreur loop : {e}")
            time.sleep(3)


if __name__ == "__main__":
    run_bot()
