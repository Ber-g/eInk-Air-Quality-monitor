#!/usr/bin/env python3
"""
AirQualityInk — Serveur API HTTP local pour contrôle à distance.
Permet à RaspCam (ou à un script externe) de piloter l'affichage,
changer de vue, naviguer dans le musée et téléverser de nouveaux tableaux.
"""
from __future__ import annotations
import cgi
import io
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import log_buffer

DEFAULT_PORT = int(os.getenv("AIRQ_API_PORT", "8088"))
DEFAULT_HOST = os.getenv("AIRQ_API_HOST", "127.0.0.1")

_BASE_DIR = Path(__file__).resolve().parent
_ARTS_DIR = _BASE_DIR / "arts"

# Plafond d'upload : au-delà, le Pi Zero 2W (512 MB) se met à swapper sur la
# carte SD pendant que la requête est bufferisée en mémoire. Une vidéo de musée
# en boucle n'a aucune raison de dépasser cette taille.
MAX_UPLOAD_BYTES = int(os.getenv("AIRQ_MAX_UPLOAD_MB", "120")) * 1024 * 1024

# Actions acceptées par /api/nav — la télécommande Telegram ne peut déclencher
# que ces mouvements, jamais une touche arbitraire.
NAV_ACTIONS = ("next", "prev", "menu", "ok", "back")


class RemoteServer:
    """Gère le serveur HTTP local et la file d'actions thread-safe pour Pygame."""

    def __init__(self, display, action_queue: queue.Queue, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.display = display
        self.action_queue = action_queue
        self.host = host
        self.port = port
        self.server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler_cls = self._make_handler()
        try:
            self.server = HTTPServer((self.host, self.port), handler_cls)
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            log_buffer.info(f"[api] Serveur HTTP local actif sur http://{self.host}:{self.port}")
        except Exception as e:
            log_buffer.warning(f"[api] Impossible de démarrer le serveur API sur {self.host}:{self.port}: {e}")

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def _make_handler(self):
        parent = self

        class APIHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Silence standard HTTP access logs to keep terminal clean
                pass

            def _send_json(self, data: dict, status: int = 200):
                payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)

            def _send_bytes(self, data: bytes, content_type: str = "image/png", status: int = 200):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)

            def _read_json_body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:
                    return {}

            def _dispatch_sync_action(self, action_type: str, **kwargs) -> dict:
                """Envoie une action à exécuter sur le thread principal et attend le résultat."""
                res_q = queue.Queue(maxsize=1)
                parent.action_queue.put((action_type, kwargs, res_q))
                try:
                    res = res_q.get(timeout=3.0)
                    return res if isinstance(res, dict) else {"success": True, "result": res}
                except queue.Empty:
                    return {"success": False, "error": "Action timeout"}

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path.rstrip("/")
                query = urllib.parse.parse_qs(parsed.query)

                if path == "" or path == "/api" or path == "/api/status":
                    status = parent.display.get_status()
                    self._send_json({"success": True, "status": status})

                elif path == "/api/screenshot":
                    # Capture d'écran synchrone via Pygame
                    res = self._dispatch_sync_action("screenshot")
                    png_bytes = res.get("png_bytes", b"")
                    if png_bytes:
                        self._send_bytes(png_bytes, "image/png")
                    else:
                        self._send_json({"success": False, "error": "Screenshot failed"}, 500)

                elif path == "/api/art/list":
                    art_page = parent.display.get_art_page()
                    images = art_page.get_all_images_list() if art_page else []
                    self._send_json({"success": True, "images": images})

                elif path == "/api/art/info":
                    art_page = parent.display.get_art_page()
                    info = art_page.get_current_info() if art_page else {}
                    self._send_json({"success": True, "art": info})

                else:
                    self._send_json({"success": False, "error": f"Endpoint GET {path} not found"}, 404)

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path.rstrip("/")
                query = urllib.parse.parse_qs(parsed.query)

                if path == "/api/view":
                    body = self._read_json_body()
                    target_view = body.get("view", query.get("view", ["aqi"])[0]).lower()
                    res = self._dispatch_sync_action("set_view", view=target_view)
                    self._send_json(res)

                elif path == "/api/art/next":
                    res = self._dispatch_sync_action("art_next")
                    self._send_json(res)

                elif path == "/api/art/prev":
                    res = self._dispatch_sync_action("art_prev")
                    self._send_json(res)

                elif path == "/api/art/select":
                    body = self._read_json_body()
                    idx = body.get("index")
                    filename = body.get("filename")
                    res = self._dispatch_sync_action("art_select", index=idx, filename=filename)
                    self._send_json(res)

                elif path == "/api/art/cartel":
                    body = self._read_json_body()
                    show = body.get("show")
                    res = self._dispatch_sync_action("art_cartel", show=show)
                    self._send_json(res)

                elif path == "/api/art/cartel_page":
                    body = self._read_json_body()
                    delta = int(body.get("delta", 1))
                    res = self._dispatch_sync_action("art_cartel_page", delta=delta)
                    self._send_json(res)

                elif path == "/api/art/upload":
                    self._handle_art_upload(query)

                elif path == "/api/art/delete":
                    body = self._read_json_body()
                    filename = body.get("filename")
                    if not filename:
                        self._send_json(
                            {"success": False, "error": "Champ 'filename' requis"}, 400
                        )
                        return
                    res = self._dispatch_sync_action("art_delete", filename=str(filename))
                    self._send_json(res)

                elif path == "/api/nav":
                    body = self._read_json_body()
                    action = str(body.get("action", "")).lower()
                    if action not in NAV_ACTIONS:
                        self._send_json(
                            {"success": False,
                             "error": f"Action inconnue. Attendu : {', '.join(NAV_ACTIONS)}"},
                            400,
                        )
                        return
                    res = self._dispatch_sync_action("nav", action=action)
                    self._send_json(res)

                elif path == "/api/station":
                    body = self._read_json_body()
                    delta = body.get("delta")
                    key = body.get("station")
                    res = self._dispatch_sync_action("station", delta=delta, key=key)
                    self._send_json(res)

                else:
                    self._send_json({"success": False, "error": f"Endpoint POST {path} not found"}, 404)

            @staticmethod
            def _sniff_extension(data: bytes) -> str | None:
                """
                Déduit l'extension des octets magiques, pas du nom de fichier.

                Le nom vient d'un message Telegram : s'y fier laisserait passer
                un `.mp4` qui est en réalité autre chose. On ne stocke que des
                formats qu'on a réellement identifiés.
                """
                if data.startswith(b"\x89PNG\r\n\x1a\n"):
                    return ".png"
                if data.startswith(b"\xff\xd8\xff"):
                    return ".jpg"
                if len(data) >= 12 and data[4:8] == b"ftyp":
                    # ISO-BMFF : mp4, m4v, mov partagent cette signature
                    brand = data[8:12]
                    return ".mov" if brand == b"qt  " else ".mp4"
                if data.startswith(b"\x1a\x45\xdf\xa3"):
                    return ".webm"   # EBML — webm ou mkv, webm pour le web
                if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"AVI ":
                    return ".avi"
                return None

            def _handle_art_upload(self, query: dict):
                """Gère l'upload d'une image ou d'une vidéo (multipart ou binaire brut)."""
                content_type = self.headers.get("Content-Type", "")
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0:
                    self._send_json({"success": False, "error": "Fichier vide"}, 400)
                    return
                if length > MAX_UPLOAD_BYTES:
                    # On refuse AVANT de lire le corps : lire 1 GB pour le jeter
                    # ensuite ferait tomber le Pi.
                    self._send_json(
                        {"success": False,
                         "error": f"Fichier trop lourd ({length // (1024*1024)} Mo, "
                                  f"max {MAX_UPLOAD_BYTES // (1024*1024)} Mo)"},
                        413,
                    )
                    return

                _ARTS_DIR.mkdir(parents=True, exist_ok=True)
                file_bytes = None
                suggested_name = None

                # 1. Cas multipart/form-data
                if "multipart/form-data" in content_type:
                    try:
                        environ = {
                            "REQUEST_METHOD": "POST",
                            "CONTENT_TYPE": content_type,
                            "CONTENT_LENGTH": str(length),
                        }
                        form = cgi.FieldStorage(
                            fp=self.rfile,
                            headers=self.headers,
                            environ=environ
                        )
                        file_item = form["file"] if "file" in form else (form["photo"] if "photo" in form else None)
                        if file_item is not None and file_item.file:
                            file_bytes = file_item.file.read()
                            if getattr(file_item, "filename", None):
                                suggested_name = file_item.filename
                    except Exception as e:
                        log_buffer.warning(f"[api] Erreur parsing multipart: {e}")

                # 2. Cas binaire brut (image/jpeg, image/png, application/octet-stream)
                if file_bytes is None:
                    file_bytes = self.rfile.read(length)
                    suggested_name = self.headers.get("X-Filename") or (query.get("filename", [None])[0])

                if not file_bytes:
                    self._send_json({"success": False, "error": "Aucune donnée image reçue"}, 400)
                    return

                # Déterminer l'extension d'après le contenu réel du fichier
                ext = self._sniff_extension(file_bytes)
                if ext is None:
                    self._send_json(
                        {"success": False,
                         "error": "Format non reconnu. Acceptés : JPEG, PNG, MP4, MOV, WebM, AVI."},
                        415,
                    )
                    return
                kind = "video" if ext in (".mp4", ".mov", ".webm", ".avi") else "image"

                if suggested_name:
                    clean_stem = re.sub(r"[^\w\s-]", "", Path(suggested_name).stem).strip().replace(" ", "_")
                    clean_name = f"{clean_stem}{ext}" if clean_stem else f"art_{int(time.time())}{ext}"
                else:
                    prefix = "video" if kind == "video" else "art"
                    clean_name = f"{prefix}_telegram_{time.strftime('%Y%m%d_%H%M%S')}{ext}"

                save_path = _ARTS_DIR / clean_name
                # Éviter d'écraser si déjà présent
                counter = 1
                while save_path.exists():
                    save_path = _ARTS_DIR / f"{save_path.stem}_{counter}{ext}"
                    counter += 1

                try:
                    save_path.write_bytes(file_bytes)
                    log_buffer.info(f"[api] Nouveau média enregistré : {save_path.name} "
                                    f"({kind}, {len(file_bytes)} octets)")
                except Exception as e:
                    self._send_json({"success": False, "error": f"Erreur écriture fichier: {e}"}, 500)
                    return

                # Exécuter l'affichage immédiat sur Pygame
                res = self._dispatch_sync_action("art_add_and_show", file_path=save_path)
                res["saved_filename"] = save_path.name
                res["kind"] = kind
                self._send_json(res)

        return APIHandler
