#!/usr/bin/env python3
"""
Module d'intégration AirQualityInk pour RaspCam.
À importer ou utiliser dans raspcam.py pour relayer les commandes Telegram
vers l'écran AirQualityInk via son API locale (127.0.0.1:8088).

Exemple d'intégration dans raspcam.py :
----------------------------------------
from raspcam_airq_plugin import (
    cmd_airq, cmd_art, cmd_art_next, cmd_art_prev,
    cmd_art_cartel, cmd_screen, handle_photo_upload,
    is_airq_command, handle_airq_command
)

# Dans votre gestionnaire de commandes Telegram :
if text.startswith("/airq"):
    send_message(chat_id, cmd_airq())
elif text.startswith("/art") or text.startswith("/musee"):
    send_message(chat_id, cmd_art())
elif text.startswith("/next") or text.startswith("/suiv"):
    send_message(chat_id, cmd_art_next())
elif text.startswith("/prev") or text.startswith("/prec"):
    send_message(chat_id, cmd_art_prev())
elif text.startswith("/cartel"):
    send_message(chat_id, cmd_art_cartel())
elif text.startswith("/screen"):
    png_bytes = cmd_screen()
    if png_bytes:
        send_photo(chat_id, photo=png_bytes)
"""
from __future__ import annotations
import io
import json
from pathlib import Path
import requests

AIRQ_API_URL = "http://127.0.0.1:8088"
TIMEOUT = 4.0


def _api_get(endpoint: str) -> dict | None:
    try:
        resp = requests.get(f"{AIRQ_API_URL}{endpoint}", timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[AirQ-Plugin] Erreur GET {endpoint}: {e}")
    return None


def _api_post(endpoint: str, data: dict | None = None) -> dict | None:
    try:
        resp = requests.post(f"{AIRQ_API_URL}{endpoint}", json=data or {}, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[AirQ-Plugin] Erreur POST {endpoint}: {e}")
    return None


def cmd_airq() -> str:
    """Bascule sur la vue Qualité de l'air et retourne un résumé textuel."""
    res = _api_post("/api/view", {"view": "aqi"})
    if not res or not res.get("success"):
        return "❌ Impossible de basculer sur l'écran AirQ (AirQualityInk est-il lancé ?)"

    status_data = _api_get("/api/status")
    if status_data and status_data.get("status"):
        st = status_data["status"]
        station = st.get("station", "Station inconnue")
        score = st.get("score", 0)
        pol = st.get("worst_pollutant", "N/A")
        val = st.get("pollutant_value", "N/A")
        label = st.get("pollutant_label", "")
        weather = st.get("weather") or {}
        temp = f"{weather.get('temperature', '?')}°C" if weather.get('temperature') is not None else ""
        rain = f" — Pluie à {weather.get('rain_at')}" if weather.get("rain_at") else ""

        msg = (
            f"🍃 *Qualité de l'air affichée*\n"
            f"• Station : *{station}*\n"
            f"• Score IQA : *{score}*\n"
            f"• Polluant majeur : *{pol}* ({val} µg/m³) - {label}\n"
        )
        if temp:
            msg += f"• Météo : *{temp}*{rain}\n"
        return msg

    return "🍃 Écran basculé sur la Qualité de l'air."


def cmd_art() -> str:
    """Bascule sur le mode Musée et retourne les infos du tableau en cours."""
    res = _api_post("/api/view", {"view": "art"})
    if not res or not res.get("success"):
        return "❌ Impossible d'afficher le Musée."
    return _format_art_info(_api_get("/api/art/info"))


def cmd_art_next() -> str:
    """Passe au tableau suivant."""
    res = _api_post("/api/art/next")
    if not res or not res.get("success"):
        return "❌ Impossible de passer au tableau suivant."
    return _format_art_info(res)


def cmd_art_prev() -> str:
    """Passe au tableau précédent."""
    res = _api_post("/api/art/prev")
    if not res or not res.get("success"):
        return "❌ Impossible de passer au tableau précédent."
    return _format_art_info(res)


def cmd_art_cartel(show: bool | None = None) -> str:
    """Bascule ou définit l'affichage du cartel."""
    data = {} if show is None else {"show": show}
    res = _api_post("/api/art/cartel", data)
    if not res or not res.get("success"):
        return "❌ Impossible de modifier l'affichage du cartel."

    is_shown = res.get("show_cartel", False)
    state_str = "affiché" if is_shown else "masqué"
    msg = f"📜 *Cartel {state_str} sur l'écran*\n\n"
    msg += _format_art_info(res)
    return msg


def cmd_art_cartel_page(delta: int = 1) -> str:
    """Change de page dans le cartel."""
    res = _api_post("/api/art/cartel_page", {"delta": delta})
    if not res or not res.get("success"):
        return "❌ Impossible de changer de page de cartel."
    page = res.get("cartel_page", 0) + 1
    return f"📜 Cartel page {page} affichée."


def cmd_art_list() -> str:
    """Liste tous les tableaux présents dans arts/."""
    res = _api_get("/api/art/list")
    if not res or not res.get("images"):
        return "🖼️ Aucun tableau trouvé dans le dossier arts/."

    images = res["images"]
    lines = ["🖼️ *Tableaux disponibles au musée :*\n"]
    for img in images:
        marker = "👉 " if img.get("is_current") else "   "
        idx = img.get("index", 0) + 1
        name = img.get("filename", "")
        lines.append(f"{marker}*{idx}.* `{name}`")
    lines.append("\nPour choisir : `/art_pick <numéro>`")
    return "\n".join(lines)


def cmd_art_select(index_or_name: int | str) -> str:
    """Sélectionne un tableau précis."""
    if isinstance(index_or_name, int) or (isinstance(index_or_name, str) and index_or_name.isdigit()):
        idx = int(index_or_name) - 1
        res = _api_post("/api/art/select", {"index": idx})
    else:
        res = _api_post("/api/art/select", {"filename": str(index_or_name)})

    if not res or not res.get("success"):
        return f"❌ Tableau introuvable : {index_or_name}"
    return _format_art_info(res)


def cmd_screen() -> bytes | None:
    """Capture l'écran Pygame et retourne les octets PNG."""
    try:
        resp = requests.get(f"{AIRQ_API_URL}/api/screenshot", timeout=TIMEOUT)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception as e:
        print(f"[AirQ-Plugin] Erreur capture d'écran : {e}")
    return None


def handle_photo_upload(photo_bytes: bytes, filename: str | None = None) -> str:
    """Téléverse une photo vers AirQualityInk pour l'afficher immédiatement."""
    try:
        headers = {"Content-Type": "image/jpeg"}
        if filename:
            headers["X-Filename"] = filename

        resp = requests.post(
            f"{AIRQ_API_URL}/api/art/upload",
            data=photo_bytes,
            headers=headers,
            timeout=10.0
        )
        if resp.status_code == 200:
            res = resp.json()
            saved = res.get("saved_filename", "inconnu")
            return (
                f"✅ *Nouveau tableau reçu et affiché !*\n"
                f"📁 Fichier : `{saved}`\n"
                f"🤖 Analyse Gemini du cartel en cours...\n\n"
                f"Tapez `/cartel` dans quelques secondes pour voir la description générée."
            )
        else:
            return f"❌ Erreur lors du téléversement : HTTP {resp.status_code}"
    except Exception as e:
        return f"❌ Impossible d'envoyer la photo à AirQualityInk : {e}"


def _format_art_info(response: dict | None) -> str:
    if not response:
        return "🖼️ Mode Musée actif."
    art = response.get("art", {})
    if not art:
        return "🖼️ Aucune œuvre disponible."

    title = art.get("title") or art.get("filename") or "Sans titre"
    artist = art.get("artist") or "Artiste inconnu"
    year = f" ({art['year']})" if art.get("year") and art["year"] != "N/A" else ""
    medium = f"\n🎨 Médium : _{art['medium']}_" if art.get("medium") and art["medium"] != "N/A" else ""
    idx = art.get("current_index", 0) + 1
    total = art.get("total_images", 0)

    cartel_state = " [Cartel affiché]" if art.get("show_cartel") else ""
    msg = f"🖼️ *Tableau {idx}/{total} : {title}*{cartel_state}\n👤 *{artist}*{year}{medium}\n"

    if art.get("contexte_oeuvre"):
        msg += f"\n📖 *L'Œuvre :*\n{art['contexte_oeuvre']}\n"
    if art.get("contexte_artiste"):
        msg += f"\n🧑‍🎨 *L'Artiste :*\n{art['contexte_artiste']}\n"

    if art.get("cartel_loading"):
        msg += "\n⏳ _Génération du cartel par Gemini en cours..._"

    return msg


def is_airq_command(text: str) -> bool:
    """Indique si un message Telegram correspond à une commande AirQualityInk."""
    if not text:
        return False
    cmd = text.strip().split()[0].lower()
    return cmd in (
        "/airq", "/aqi", "/qualite",
        "/art", "/musee", "/musée",
        "/next", "/suiv", "/suivant",
        "/prev", "/prec", "/precedent",
        "/cartel", "/cartel_next", "/cartel_prev",
        "/art_list", "/arts", "/list",
        "/art_pick", "/select",
        "/screen", "/capture", "/screenshot",
        "/airq_help"
    )


def handle_airq_command(text: str) -> tuple[str, bytes | None]:
    """
    Traite une commande texte et retourne un tuple (message_text, optional_photo_bytes).
    Permet une intégration en 1 seule ligne dans raspcam.py !
    """
    parts = text.strip().split()
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/airq", "/aqi", "/qualite"):
        return cmd_airq(), None
    elif cmd in ("/art", "/musee", "/musée"):
        return cmd_art(), None
    elif cmd in ("/next", "/suiv", "/suivant"):
        return cmd_art_next(), None
    elif cmd in ("/prev", "/prec", "/precedent"):
        return cmd_art_prev(), None
    elif cmd == "/cartel":
        return cmd_art_cartel(), None
    elif cmd == "/cartel_next":
        return cmd_art_cartel_page(1), None
    elif cmd == "/cartel_prev":
        return cmd_art_cartel_page(-1), None
    elif cmd in ("/art_list", "/arts", "/list"):
        return cmd_art_list(), None
    elif cmd in ("/art_pick", "/select"):
        if not arg:
            return "Usage: `/art_pick <numéro>` (ex: `/art_pick 2`)", None
        return cmd_art_select(arg), None
    elif cmd in ("/screen", "/capture", "/screenshot"):
        png = cmd_screen()
        if png:
            return "📸 Capture de l'écran en direct :", png
        return "❌ Impossible de capturer l'écran.", None
    elif cmd == "/airq_help":
        help_text = (
            "📱 *Commandes AirQualityInk :*\n\n"
            "🍃 *Qualité de l'air :*\n"
            "• `/airq` : Affiche la qualité de l'air & météo\n\n"
            "🖼️ *Musée d'Art :*\n"
            "• `/art` : Affiche le musée d'art\n"
            "• `/next` : Tableau suivant\n"
            "• `/prev` : Tableau précédent\n"
            "• `/cartel` : Affiche / masque le cartel explicatif\n"
            "• `/list` : Liste tous les tableaux\n"
            "• `/art_pick <N>` : Affiche le tableau N\n\n"
            "📤 *Téléversement :*\n"
            "• Envoyez directement une photo pour l'afficher sur l'écran !\n\n"
            "📸 *Écran :*\n"
            "• `/screen` : Reçoit une capture d'écran du moniteur"
        )
        return help_text, None

    return "Commande AirQ inconnue.", None
