#!/usr/bin/env python3
"""
Page Musée — galerie d'œuvres (images fixes + vidéos en boucle) avec cartel
généré par IA.

Deux types de média cohabitent dans une même playlist triée :
  • image : décodée par Pygame, mise à l'échelle et centrée
  • vidéo : décodée par un process ffmpeg qui alimente la boucle de rendu en
    frames RGB24, en boucle infinie (voir video_player.py)

Le cartel est généré une fois par média, mis en cache dans un `.json` voisin.
Si l'IA ne reconnaît pas l'œuvre (photo personnelle, capture d'écran), elle
bascule sur un cartel humoristique plutôt que d'inventer des faits.
"""
from __future__ import annotations
import base64
from datetime import date
import json
import math
import os
from pathlib import Path
import random
import threading
import requests
import pygame
from dotenv import load_dotenv
from pages.base import BasePage, NavAction
import log_buffer
import video_player

# ── Résolution des chemins ───────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BASE_DIR / ".env"
load_dotenv(_ENV_FILE if _ENV_FILE.exists() else None, override=True)

_ARTS_DIR = _BASE_DIR / "arts"

# ── Configuration Gemini REST API ─────────────────────────────────────────────
DEFAULT_MODEL = "gemini-3.5-flash"
# "gemini-flash-latest" a été retiré : c'est un alias non-versionné qui peut
# être ré-aiguillé par Google vers un modèle expérimental ou déprécié, ce qui
# casse silencieusement en 404 (cf. issues connues côté SDK Google).
# "gemini-3-flash-preview" a été retiré faute de confirmation comme identifiant stable.
# À réévaluer périodiquement : les modèles Gemini sont dépréciés régulièrement.
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
VALID_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]

# ── Marges (Écran 800x480 / 800x600) ─────────────────────────────────────────
MARGIN_TOP    = 15
MARGIN_BOTTOM = 20
MARGIN_LEFT   = 48
MARGIN_RIGHT  = 50

# ── Cartel ───────────────────────────────────────────────────────────────────
CARTEL_PROMPT = (
    "Tu es conservateur de musée. Examine ce média et rédige son cartel.\n\n"
    "DEUX CAS, et un seul :\n"
    "1. Tu reconnais une œuvre répertoriée (peinture, sculpture, photographie "
    "ou film connu) : rédige un cartel FACTUEL et vérifiable.\n"
    "2. Tu ne la reconnais pas (photo personnelle, capture d'écran, image "
    "banale ou ambiguë) : n'invente AUCUN fait réel. Rédige à la place un "
    "cartel HUMORISTIQUE, pince-sans-rire, qui traite le sujet comme un "
    "chef-d'œuvre majeur — titre pompeux, mouvement artistique inventé et "
    "assumé, analyse d'une gravité comique. Reste bienveillant : jamais de "
    "moquerie sur une personne visible à l'image.\n\n"
    "Réponds EXCLUSIVEMENT en JSON strict avec ces clés exactement :\n"
    "- 'reconnue': true si cas 1, false si cas 2\n"
    "- 'ton': 'factuel' ou 'humoristique'\n"
    "- 'titre': titre de l'œuvre en français\n"
    "- 'artiste': nom complet de l'artiste\n"
    "- 'annee': année ou siècle de création\n"
    "- 'matiere': médium ou support\n"
    "- 'contexte_oeuvre': 2 phrases sur le sujet ou l'histoire de l'œuvre\n"
    "- 'contexte_artiste': 2 phrases sur la vie ou le style de l'artiste"
)


# ── Provenance d'un cartel ───────────────────────────────────────────────────
# Écrite dans le `.json` voisin du média. Elle survit au redémarrage, ce qu'un
# simple drapeau en mémoire ne ferait pas : si l'app tombe pendant que Gemini
# travaille, le titre donné par l'expéditeur serait perdu.
SOURCE_PENDING = "ia_en_attente"   # amorce posée à l'upload, Gemini doit compléter
SOURCE_AI      = "ia"              # cartel rédigé par Gemini
SOURCE_MANUAL  = "manuel"          # saisi à la main, Gemini ne sera jamais appelé


def _write_cartel(json_path: Path, data: dict) -> bool:
    """Écrit un cartel sur disque. Retourne False sans lever si l'écriture échoue."""
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_buffer.warning(f"[art] cartel non écrit {json_path.name} : {e}")
        return False


def _cartel_stub(path: Path, title: str | None, no_ai: bool) -> dict:
    """
    Cartel d'amorce, posé dès l'upload.

    Il porte le titre voulu par l'expéditeur et dit si Gemini doit encore passer.
    `titre_verrouille` est la garantie que l'IA ne renommera pas l'œuvre : elle
    peut tout réécrire sauf ça.
    """
    return {
        "reconnue": False,
        "ton": "indisponible",
        "titre": (title or path.stem.replace("_", " ")).strip(),
        "titre_verrouille": bool(title),
        "source": SOURCE_MANUAL if no_ai else SOURCE_PENDING,
        "artiste": "",
        "annee": "",
        "matiere": "Vidéo" if video_player.is_video(path) else "",
        "contexte_oeuvre": "",
        "contexte_artiste": "",
    }


def _fallback_cartel(path: Path, artiste: str, oeuvre: str, artiste_txt: str) -> dict:
    """Cartel minimal affiché quand l'IA est indisponible — jamais de page vide."""
    return {
        "reconnue": False,
        "ton": "indisponible",
        "titre": path.stem.replace("_", " ").title(),
        "artiste": artiste,
        "annee": "N/A",
        "matiere": "Vidéo" if video_player.is_video(path) else "N/A",
        "contexte_oeuvre": oeuvre,
        "contexte_artiste": artiste_txt,
    }



def _fit_text(text: str, font: "pygame.font.Font", max_width: int) -> str:
    """
    Tronque `text` pour qu'il tienne dans `max_width`, suffixe compris.

    Les messages d'erreur de ffmpeg contiennent un chemin absolu et dépassent
    largement les 720 px du CRT : sans ça, la ligne sort de l'écran des deux
    côtés et devient illisible au moment précis où elle sert à quelque chose.
    """
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid] + ellipsis)[0] <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ellipsis


class ArtPage(BasePage):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.media_paths: list[Path] = []
        self.current_index: int = 0
        self.current_kind: str = "image"          # "image" | "video"
        self.current_surface: pygame.Surface | None = None
        self._scaled_surface: pygame.Surface | None = None
        self._scaled_pos: tuple[int, int] = (0, 0)
        self._scaled_screen_size: tuple[int, int] = (0, 0)
        self._media_loaded: bool = False
        # Frame vidéo courante. `_video_frame_seq` vient du player : tant qu'il
        # ne bouge pas, on re-blitte la Surface déjà convertie au lieu d'en
        # reconstruire une à chacun des 30 tours/s de la boucle de rendu.
        self._video_surface: pygame.Surface | None = None
        self._video_frame_seq: int = -1
        self._video_pos: tuple[int, int] = (0, 0)

        self.show_cartel: bool = False
        self.current_cartel: dict | None = None
        self.cartel_loading: bool = False
        self.cartel_page: int = 0
        self.cartel_max_page: int = 0
        self._displayed_path: Path | None = None  # média actuellement affiché
        self._fetching: set[Path] = set()         # fetchs Gemini déjà en vol
        self._overlay_surface: pygame.Surface | None = None
        self._overlay_size: tuple[int, int] = (0, 0)

    # ── Cycle de vie de la page ──────────────────────────────────────────────

    def on_enter(self, context: dict) -> None:
        super().on_enter(context)
        # Reprend la lecture si on revient sur la page alors qu'une vidéo est
        # le média courant (le player a été tué en quittant la page).
        self._ensure_loaded()
        if self.current_kind == "video" and self._displayed_path is not None:
            if not video_player.player.is_playing():
                self._reset_video_frame()
                video_player.player.play(self._displayed_path)

    def on_exit(self) -> None:
        # Sans ça ffmpeg continuerait de décoder — et de consommer un cœur —
        # pendant qu'on regarde une autre page.
        video_player.player.stop()
        self._reset_video_frame()

    def _reset_video_frame(self) -> None:
        self._video_surface = None
        self._video_frame_seq = -1

    # ── Chargement ───────────────────────────────────────────────────────────

    def _scan_media_dir(self) -> list[Path]:
        """Liste triée des médias d'`arts/`. Les vignettes (.thumbs/) sont ignorées."""
        art_dir = _ARTS_DIR if _ARTS_DIR.exists() else Path("arts")
        if not art_dir.exists():
            return []
        return sorted(
            p for p in art_dir.iterdir()
            if p.is_file() and video_player.is_media(p)
        )

    def _load_media_files(self) -> None:
        self.media_paths = self._scan_media_dir()
        if not self.media_paths:
            return
        # Œuvre du jour : même média toute la journée, change à minuit.
        today_seed = date.today().toordinal()
        self.current_index = random.Random(today_seed).randint(0, len(self.media_paths) - 1)
        self._load_current_media()

    def _load_current_media(self) -> None:
        if not self.media_paths:
            self.current_surface = None
            self._scaled_surface = None
            self.current_cartel = None
            self._displayed_path = None
            video_player.player.stop()
            return

        self.show_cartel = False
        self.cartel_page = 0
        self.cartel_max_page = 0
        self._scaled_surface = None
        self.current_surface = None
        self._reset_video_frame()

        path = self.media_paths[self.current_index]
        self._displayed_path = path
        self.current_kind = "video" if video_player.is_video(path) else "image"

        if self.current_kind == "video":
            # Boucle infinie — exigence produit : une vidéo ne s'arrête jamais
            # d'elle-même, seul un changement de média la coupe.
            video_player.player.play(path)
        else:
            video_player.player.stop()
            try:
                self.current_surface = pygame.image.load(str(path)).convert_alpha()
            except Exception as e:
                log_buffer.warning(f"[art] chargement {path.name} échoué : {e}")
                self.current_surface = None

        self._load_or_fetch_cartel(path)

    def _ensure_loaded(self) -> None:
        """Charge la liste des médias une seule fois, à la demande (lazy loading)."""
        if not self._media_loaded:
            self._load_media_files()
            self._media_loaded = True

    def _refresh_media_list(self, keep: Path | None = None) -> None:
        """Re-scanne `arts/` et recale `current_index` sur `keep` si fourni."""
        self.media_paths = self._scan_media_dir()
        self._media_loaded = True
        if not self.media_paths:
            self.current_index = 0
            return
        if keep is not None:
            target = keep.resolve()
            for i, p in enumerate(self.media_paths):
                if p.resolve() == target or p.name == keep.name:
                    self.current_index = i
                    return
        self.current_index = min(self.current_index, len(self.media_paths) - 1)

    # ── Cartel ───────────────────────────────────────────────────────────────

    def _load_or_fetch_cartel(self, media_path: Path) -> None:
        """Lit le cache JSON local (si toujours valide) ou lance la génération en arrière-plan."""
        json_path = media_path.with_suffix(".json")

        # Le cache n'est valide que si le JSON est plus récent que le média :
        # si le fichier a été remplacé en gardant le même nom, on régénère
        # au lieu d'afficher un cartel obsolète.
        cache_is_valid = False
        if json_path.exists():
            try:
                cache_is_valid = json_path.stat().st_mtime >= media_path.stat().st_mtime
            except OSError:
                cache_is_valid = False

        if cache_is_valid:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
            except Exception as e:
                log_buffer.warning(f"[art] cache JSON illisible {json_path.name} : {e}")
            else:
                self.current_cartel = cached
                # Une amorce n'est pas un cartel fini : on affiche son titre tout
                # de suite — l'écran n'attend pas le réseau — et Gemini complète
                # le reste en tâche de fond. Un cartel manuel, lui, est définitif.
                if cached.get("source") != SOURCE_PENDING:
                    self.cartel_loading = False
                    return
                self.cartel_loading = True
                if media_path in self._fetching:
                    return
                self._fetching.add(media_path)
                threading.Thread(
                    target=self._fetch_cartel_from_gemini,
                    args=(media_path, json_path),
                    daemon=True,
                ).start()
                return

        self.current_cartel = None
        self.cartel_loading = True

        # Évite de relancer un fetch pour le même média si une requête est déjà
        # en vol (ex: double appui rapide, ou retour rapide sur ce même média).
        # Le thread déjà lancé mettra à jour l'affichage dès qu'il aura terminé,
        # tant que ce média est toujours affiché (voir _displayed_path).
        if media_path in self._fetching:
            return
        self._fetching.add(media_path)

        threading.Thread(
            target=self._fetch_cartel_from_gemini,
            args=(media_path, json_path),
            daemon=True,
        ).start()

    def _cartel_source_image(self, media_path: Path) -> Path | None:
        """Image à envoyer à l'IA : le média lui-même, ou une vignette pour une vidéo."""
        if not video_player.is_video(media_path):
            return media_path
        return video_player.extract_thumbnail(media_path)

    def _fetch_cartel_from_gemini(self, media_path: Path, json_path: Path) -> None:
        """Interroge l'API REST Gemini sans bloquer le rendu Pygame."""
        if media_path != self._displayed_path:
            # L'utilisateur a déjà changé de média entre le clic et le
            # démarrage réel du thread : inutile de consommer du quota API.
            log_buffer.info(f"[art] cartel {media_path.name} abandonné (média changé au démarrage)")
            self._fetching.discard(media_path)
            return

        log_buffer.info(f"[art] cartel {media_path.name} : interrogation de Gemini")

        api_key = os.environ.get("GEMINI_API_KEY", "").strip('"\' \t\r\n')
        raw_model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip('"\' \t\r\n')
        model_name = raw_model if raw_model in VALID_MODELS else DEFAULT_MODEL

        if not api_key:
            if media_path == self._displayed_path:
                self.current_cartel = _fallback_cartel(
                    media_path,
                    "Artiste inconnu",
                    "Clé GEMINI_API_KEY manquante dans le fichier .env.",
                    "Ajoutez votre clé API dans .env pour activer l'analyse.",
                )
                self.cartel_loading = False
            self._fetching.discard(media_path)
            return

        try:
            source = self._cartel_source_image(media_path)
            if source is None:
                raise RuntimeError("vignette vidéo indisponible (ffmpeg manquant ?)")

            image_bytes = source.read_bytes()
            base64_data = base64.b64encode(image_bytes).decode("utf-8")
            mime_type = "image/png" if source.suffix.lower() == ".png" else "image/jpeg"

            prompt = CARTEL_PROMPT
            if video_player.is_video(media_path):
                prompt += (
                    "\n\nATTENTION : cette image est une capture extraite d'une "
                    "vidéo diffusée en boucle. Rédige le cartel pour la vidéo, "
                    "pas pour l'image fixe."
                )

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": base64_data}}
                    ]
                }],
                # Température plus haute que l'ancienne 0.2 : le cas humoristique
                # a besoin d'un peu de latitude, le cas factuel reste cadré par
                # la consigne « vérifiable ».
                "generationConfig": {"temperature": 0.6, "response_mime_type": "application/json"}
            }

            headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
            models_to_try = [model_name] + [m for m in FALLBACK_MODELS if m != model_name]
            resp = None
            last_err = ""

            for try_model in models_to_try:
                if media_path != self._displayed_path:
                    # Annulé pendant la boucle de fallback. Sans cette trace, un
                    # cartel qui ne se génère jamais ne laisse aucune explication.
                    log_buffer.info(f"[art] cartel {media_path.name} annulé (média changé)")
                    return

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{try_model}:generateContent"
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        break
                    last_err = resp.text
                except Exception as req_ex:
                    last_err = str(req_ex)

            if resp is None or resp.status_code != 200:
                raise RuntimeError(last_err[:200])

            raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            data = json.loads(raw_text)

            # Normalise : un modèle peut renvoyer 'ton' sans 'reconnue', ou l'inverse.
            data["reconnue"] = bool(data.get("reconnue", True))
            if data.get("ton") not in ("factuel", "humoristique"):
                data["ton"] = "factuel" if data["reconnue"] else "humoristique"

            # Le titre donné par l'expéditeur prime sur celui de l'IA. Gemini a le
            # droit de tout rédiger, pas de rebaptiser une œuvre que quelqu'un a
            # déjà nommée : c'est sous ce nom qu'elle a été envoyée et qu'elle sera
            # cherchée dans la liste.
            stub = self._read_cartel(json_path)
            if stub.get("titre_verrouille") and stub.get("titre"):
                data["titre"] = stub["titre"]
                data["titre_verrouille"] = True
            data["source"] = SOURCE_AI

            _write_cartel(json_path, data)

            if media_path == self._displayed_path:
                self.current_cartel = data

        except Exception as e:
            log_buffer.warning(f"[art] cartel {media_path.name} échoué : {e}")
            if media_path == self._displayed_path:
                self.current_cartel = _fallback_cartel(
                    media_path,
                    "Analyse indisponible",
                    "Impossible de générer le cartel pour le moment.",
                    f"Détail : {e}",
                )
        finally:
            self._fetching.discard(media_path)
            if media_path == self._displayed_path:
                self.cartel_loading = False

    # ── Entrées clavier ──────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> NavAction:
        if event.type != pygame.KEYDOWN:
            return NavAction.NONE

        if event.key == pygame.K_ESCAPE:
            if self.show_cartel:
                self.show_cartel = False
                self.cartel_page = 0
                return NavAction.NONE
            return NavAction.BACK

        elif event.key == pygame.K_RIGHT:
            if self.media_paths:
                self.current_index = (self.current_index + 1) % len(self.media_paths)
                self._load_current_media()
            return NavAction.NONE

        elif event.key == pygame.K_LEFT:
            if self.media_paths:
                self.current_index = (self.current_index - 1) % len(self.media_paths)
                self._load_current_media()
            return NavAction.NONE

        elif event.key == pygame.K_DOWN:
            if not self.show_cartel:
                self.show_cartel = True
                self.cartel_page = 0
            elif self.cartel_page < self.cartel_max_page:
                self.cartel_page += 1
            else:
                self.show_cartel = False
                self.cartel_page = 0
            return NavAction.NONE

        elif event.key == pygame.K_UP:
            if not self.show_cartel:
                self.show_cartel = True
                self.cartel_page = 0
            elif self.cartel_page > 0:
                self.cartel_page -= 1
            else:
                self.show_cartel = False
                self.cartel_page = 0
            return NavAction.NONE

        return super().handle_event(event)

    # ── API publique (pilotage distant) ──────────────────────────────────────

    def next_image(self) -> dict:
        self._ensure_loaded()
        if self.media_paths:
            self.current_index = (self.current_index + 1) % len(self.media_paths)
            self._load_current_media()
        return self.get_current_info()

    def prev_image(self) -> dict:
        self._ensure_loaded()
        if self.media_paths:
            self.current_index = (self.current_index - 1) % len(self.media_paths)
            self._load_current_media()
        return self.get_current_info()

    def set_image_by_index(self, idx: int) -> dict:
        self._ensure_loaded()
        if self.media_paths and 0 <= idx < len(self.media_paths):
            self.current_index = idx
            self._load_current_media()
        return self.get_current_info()

    def set_image_by_name(self, name: str) -> dict:
        self._ensure_loaded()
        for i, p in enumerate(self.media_paths):
            if p.name.lower() == name.lower() or p.stem.lower() == name.lower():
                self.current_index = i
                self._load_current_media()
                break
        return self.get_current_info()

    def toggle_cartel(self, show: bool | None = None) -> bool:
        if show is None:
            self.show_cartel = not self.show_cartel
        else:
            self.show_cartel = bool(show)
        self.cartel_page = 0
        return self.show_cartel

    def change_cartel_page(self, delta: int) -> int:
        if not self.show_cartel:
            self.show_cartel = True
            self.cartel_page = 0
        else:
            self.cartel_page = max(0, min(self.cartel_page + delta, self.cartel_max_page))
        return self.cartel_page

    def add_and_display_image(
        self, media_path: Path, title: str | None = None, no_ai: bool = False
    ) -> dict:
        """
        Ajoute ou rafraîchit la liste de médias et affiche immédiatement celui-ci.

        L'amorce de cartel est écrite AVANT le chargement : c'est elle que
        `_load_or_fetch_cartel` lira juste après pour savoir s'il doit appeler
        Gemini, et quel titre protéger s'il l'appelle.
        """
        if title or no_ai:
            _write_cartel(
                media_path.with_suffix(".json"), _cartel_stub(media_path, title, no_ai)
            )
        self._refresh_media_list(keep=media_path)
        self._load_current_media()
        return self.get_current_info()

    def _resolve_media(self, filename: str) -> tuple[Path | None, str]:
        """
        Résout un nom de fichier reçu de l'extérieur en chemin sûr dans `arts/`.

        Le nom vient d'un message Telegram : sans ce garde-fou, un `../` donnerait
        accès à tout le disque. Rend (chemin, "") ou (None, raison du refus).
        """
        target = (_ARTS_DIR / filename).resolve()
        if target.parent != _ARTS_DIR.resolve():
            return None, "Chemin de fichier refusé."
        if not target.is_file():
            return None, f"Média introuvable : {filename}"
        if not video_player.is_media(target):
            return None, "Ce fichier n'est pas un média du musée."
        return target, ""

    @staticmethod
    def _read_cartel(json_path: Path) -> dict:
        """Lit un cartel sur disque. Rend un dict vide plutôt que de lever."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_cartel(self, filename: str, fields: dict) -> dict:
        """
        Écrit un cartel saisi à la main, en lieu et place de celui de l'IA.

        Fusionne avec ce qui existe déjà : l'expéditeur répond champ par champ et
        peut en sauter, un champ sauté ne doit pas effacer ce qui était là. Le
        cartel passe en `manuel` — Gemini ne sera plus jamais appelé pour ce média,
        ce qui est tout l'intérêt pour une œuvre marquée confidentielle.
        """
        target, error = self._resolve_media(filename)
        if target is None:
            return {"success": False, "error": error}

        json_path = target.with_suffix(".json")
        cartel = self._read_cartel(json_path) or _cartel_stub(target, None, True)

        for key in ("titre", "artiste", "annee", "contexte_oeuvre"):
            value = (fields.get(key) or "").strip()
            if value:
                cartel[key] = value

        if fields.get("titre"):
            cartel["titre_verrouille"] = True
        cartel["source"] = SOURCE_MANUAL
        cartel["ton"] = "factuel"
        cartel["reconnue"] = False
        cartel.setdefault("matiere", "Vidéo" if video_player.is_video(target) else "")
        cartel.setdefault("contexte_artiste", "")

        if not _write_cartel(json_path, cartel):
            return {"success": False, "error": "Écriture du cartel impossible."}

        # Le média affiché doit refléter le nouveau cartel sans attendre un
        # changement de page.
        if self._displayed_path is not None and self._displayed_path.resolve() == target:
            self.current_cartel = cartel
            self.cartel_loading = False

        log_buffer.info(f"[art] cartel manuel enregistré : {target.name}")
        return {"success": True, "filename": target.name, "cartel": cartel}

    def delete_media(self, filename: str) -> dict:
        """
        Supprime définitivement un média et ses fichiers dérivés.

        La suppression se fait par NOM, jamais par index : entre le moment où
        l'utilisateur demande « supprime 5 » et celui où il confirme, la liste
        peut avoir bougé (upload concurrent). Supprimer par index effacerait
        alors le mauvais fichier.
        """
        self._ensure_loaded()

        target, error = self._resolve_media(filename)
        if target is None:
            return {"success": False, "error": error}

        was_current = (
            self._displayed_path is not None
            and self._displayed_path.resolve() == target
        )
        # Un player lisant un inode supprimé resterait en vie en plein écran.
        video_player.player.stop_if_playing(target)

        derived = [target.with_suffix(".json"), video_player.thumbnail_path(target)]
        try:
            target.unlink()
        except OSError as e:
            return {"success": False, "error": f"Suppression impossible : {e}"}

        for extra in derived:
            try:
                extra.unlink(missing_ok=True)
            except OSError as e:
                log_buffer.warning(f"[art] fichier dérivé non supprimé {extra.name} : {e}")

        log_buffer.info(f"[art] média supprimé : {target.name}")

        keep = None if was_current else self._displayed_path
        self._refresh_media_list(keep=keep)
        self._load_current_media()

        return {
            "success": True,
            "deleted": target.name,
            "remaining": len(self.media_paths),
            "art": self.get_current_info(),
        }

    # ── Introspection ────────────────────────────────────────────────────────

    def get_current_info(self) -> dict:
        self._ensure_loaded()
        if not self.media_paths or self.current_index >= len(self.media_paths):
            return {
                "active": False,
                "current_index": 0,
                "total_images": 0,
                "filename": "",
                "kind": "image",
                "is_video": False,
                "video_playing": False,
                "video_error": None,
                "title": "Aucune œuvre",
                "artist": "",
                "year": "",
                "medium": "",
                "tone": None,
                "recognised": None,
                "contexte_oeuvre": "",
                "contexte_artiste": "",
                "show_cartel": self.show_cartel,
                "cartel_page": self.cartel_page,
                "cartel_max_page": self.cartel_max_page,
                "cartel_loading": self.cartel_loading,
            }
        cur_path = self.media_paths[self.current_index]
        c = self.current_cartel
        is_video = self.current_kind == "video"
        return {
            "active": True,
            "current_index": self.current_index,
            "total_images": len(self.media_paths),
            "filename": cur_path.name,
            "kind": self.current_kind,
            "is_video": is_video,
            # `status()` est relu ici, et non un booléen posé au lancement :
            # ffmpeg peut mourir après un démarrage réussi, et l'API doit le dire.
            "video_status": (video_player.player.status() if is_video else None),
            "video_playing": is_video and video_player.player.status() == video_player.STATUS_PLAYING,
            "video_error": (
                video_player.player.last_error
                if is_video and video_player.player.status() == video_player.STATUS_ERROR
                else None
            ),
            "title": (c.get("titre") if c else cur_path.stem.replace("_", " ").title()),
            "artist": (c.get("artiste") if c else "Artiste inconnu"),
            "year": (c.get("annee") if c else ""),
            "medium": (c.get("matiere") if c else ""),
            "tone": (c.get("ton") if c else None),
            "recognised": (c.get("reconnue") if c else None),
            "contexte_oeuvre": (c.get("contexte_oeuvre") if c else ""),
            "contexte_artiste": (c.get("contexte_artiste") if c else ""),
            "show_cartel": self.show_cartel,
            "cartel_page": self.cartel_page,
            "cartel_max_page": self.cartel_max_page,
            "cartel_loading": self.cartel_loading,
        }

    def get_all_images_list(self) -> list[dict]:
        self._ensure_loaded()
        return [
            {
                "index": i,
                "filename": p.name,
                "kind": "video" if video_player.is_video(p) else "image",
                "is_current": (i == self.current_index),
            }
            for i, p in enumerate(self.media_paths)
        ]

    # ── Rendu ────────────────────────────────────────────────────────────────

    def _wrap_lines(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        """Découpe un texte en liste de lignes selon la largeur disponible."""
        if not text:
            return []
        lines = []
        for paragraph in str(text).splitlines():
            words = [w for w in paragraph.split(" ") if w]
            current_line = []
            for word in words:
                test_line = " ".join(current_line + [word])
                if font.size(test_line)[0] <= max_width or not current_line:
                    current_line.append(word)
                else:
                    lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
        return lines

    def _layout_cartel_content(self, c: dict, f_title: pygame.font.Font,
                               f_sub: pygame.font.Font, f_body: pygame.font.Font,
                               max_w: int) -> tuple[list[tuple], int]:
        """Pré-calcule la position verticale de chaque élément du cartel."""
        items = []
        cur_y = 0

        # Titre
        titre = str(c.get("titre", "Sans titre"))
        for line in self._wrap_lines(titre, f_title, max_w):
            items.append(("text", line, f_title, (20, 20, 20), cur_y))
            cur_y += f_title.get_height() + 3
        cur_y += 2

        # Artiste, Année, Médium
        artiste = str(c.get("artiste", "Artiste inconnu"))
        annee = str(c.get("annee", "N/A"))
        matiere = str(c.get("matiere", ""))
        meta_parts = [artiste]
        if annee and annee != "N/A":
            meta_parts[0] += f" ({annee})"
        if matiere and matiere != "N/A":
            meta_parts.append(matiere)

        for line in self._wrap_lines(" — ".join(meta_parts), f_sub, max_w):
            items.append(("text", line, f_sub, (90, 85, 80), cur_y))
            cur_y += f_sub.get_height() + 2
        cur_y += 8

        # Ligne de séparation
        items.append(("line", cur_y))
        cur_y += 12

        # L'Œuvre
        oeuvre = c.get("contexte_oeuvre", "")
        if oeuvre:
            items.append(("text", "L'Œuvre :", f_sub, (40, 40, 40), cur_y))
            cur_y += f_sub.get_height() + 4
            for line in self._wrap_lines(str(oeuvre), f_body, max_w):
                items.append(("text", line, f_body, (50, 50, 50), cur_y))
                cur_y += f_body.get_height() + 4
            cur_y += 10

        # L'Artiste
        artiste_txt = c.get("contexte_artiste", "")
        if artiste_txt:
            items.append(("text", "L'Artiste :", f_sub, (40, 40, 40), cur_y))
            cur_y += f_sub.get_height() + 4
            for line in self._wrap_lines(str(artiste_txt), f_body, max_w):
                items.append(("text", line, f_body, (50, 50, 50), cur_y))
                cur_y += f_body.get_height() + 4

        # Mention de ton — discrète, en bas, dans le gris le plus clair du cartel.
        # Le visiteur doit pouvoir distinguer un fait d'une invention sans que
        # la page crie « ATTENTION FAUX » : c'est une note de bas de page, pas
        # un bandeau d'avertissement.
        if c.get("ton") == "humoristique":
            cur_y += 12
            items.append(("line", cur_y))
            cur_y += 10
            note = "Œuvre non répertoriée — cartel de fantaisie."
            for line in self._wrap_lines(note, f_body, max_w):
                items.append(("text", line, f_body, (150, 145, 135), cur_y))
                cur_y += f_body.get_height() + 3

        return items, max(1, cur_y)

    def _render_cartel(self, screen: pygame.Surface, w: int, h: int, fonts: dict) -> None:
        try:
            cartel_w = min(int(w * 0.88), 680)
            cartel_h = min(int(h * 0.88), 440)
            cx = (w - cartel_w) // 2
            cy = (h - cartel_h) // 2

            # Fond assombri
            if self._overlay_surface is None or self._overlay_size != (w, h):
                self._overlay_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                self._overlay_surface.fill((0, 0, 0, 185))
                self._overlay_size = (w, h)
            screen.blit(self._overlay_surface, (0, 0))

            # Carte musée
            card = pygame.Surface((cartel_w, cartel_h))
            card.fill((250, 248, 245))
            screen.blit(card, (cx, cy))
            pygame.draw.rect(screen, (195, 190, 180), (cx, cy, cartel_w, cartel_h), 2)

            pad_x = 24
            pad_y_top = 20
            footer_h = 32
            content_w = cartel_w - (pad_x * 2) - 14
            view_h = cartel_h - pad_y_top - footer_h

            f_title = fonts.get("large") or pygame.font.Font(None, 24)
            f_sub   = fonts.get("italic") or fonts.get("small") or pygame.font.Font(None, 15)
            f_body  = fonts.get("small") or pygame.font.Font(None, 14)

            if self.cartel_loading:
                lbl = f_title.render("Analyse de l'œuvre en cours...", True, (80, 80, 80))
                sub = f_sub.render("Génération du cartel ...", True, (120, 120, 120))
                screen.blit(lbl, (cx + pad_x, cy + cartel_h // 2 - 25))
                screen.blit(sub, (cx + pad_x, cy + cartel_h // 2 + 10))
                return

            if not self.current_cartel:
                lbl = f_body.render("Aucune information disponible pour cette œuvre.", True, (100, 100, 100))
                screen.blit(lbl, (cx + pad_x, cy + cartel_h // 2))
                return

            # Disposition et pagination
            items, total_h = self._layout_cartel_content(self.current_cartel, f_title, f_sub, f_body, content_w)
            overflow = max(0, total_h - view_h)
            page_step = max(60, view_h - 40)
            self.cartel_max_page = max(1, math.ceil(overflow / page_step)) if overflow > 0 else 0
            self.cartel_page = max(0, min(self.cartel_page, self.cartel_max_page))
            scroll_y = int((overflow * self.cartel_page) / max(1, self.cartel_max_page)) if self.cartel_max_page > 0 else 0

            # Rendu direct sécurisé par rectangle de découpe
            content_left = cx + pad_x
            content_top = cy + pad_y_top
            screen.set_clip(pygame.Rect(content_left, content_top, content_w, view_h))

            for item in items:
                kind = item[0]
                if kind == "text":
                    _, line_text, font_obj, color, item_y = item
                    if line_text:
                        draw_y = content_top + item_y - scroll_y
                        if content_top - font_obj.get_height() <= draw_y <= content_top + view_h:
                            screen.blit(font_obj.render(line_text, True, color), (content_left, draw_y))
                elif kind == "line":
                    _, line_y = item
                    draw_y = content_top + line_y - scroll_y
                    if content_top <= draw_y <= content_top + view_h:
                        pygame.draw.line(screen, (215, 210, 200), (content_left, draw_y), (content_left + content_w, draw_y), 1)

            screen.set_clip(None)

            # Ascenseur
            if self.cartel_max_page > 0:
                bar_x = cx + cartel_w - 14
                bar_y = content_top
                pygame.draw.rect(screen, (225, 220, 210), (bar_x, bar_y, 4, view_h))
                thumb_h = max(20, int(view_h * (view_h / max(1, total_h))))
                thumb_y = bar_y + int((view_h - thumb_h) * (self.cartel_page / max(1, self.cartel_max_page)))
                pygame.draw.rect(screen, (150, 145, 135), (bar_x, thumb_y, 4, thumb_h))

            # Pied de carte
            f_small = fonts.get("small") or pygame.font.Font(None, 12)
            nav_lbl = f_small.render("[◄ / ►] Naviguer", True, (150, 145, 135))
            screen.blit(nav_lbl, (cx + pad_x, cy + cartel_h - 22))

            if self.cartel_max_page > 0:
                page_lbl = f_small.render(f"Page {self.cartel_page + 1}/{self.cartel_max_page + 1}", True, (120, 115, 105))
                screen.blit(page_lbl, (cx + (cartel_w - page_lbl.get_width()) // 2, cy + cartel_h - 22))

                if self.cartel_page == 0:
                    hint_str = "[▲] Fermer  [▼] Page suivante"
                elif self.cartel_page >= self.cartel_max_page:
                    hint_str = "[▲] Page précédente  [▼] Fermer"
                else:
                    hint_str = "[▲] Précédent  [▼] Suivant"

                act_lbl = f_small.render(hint_str, True, (110, 105, 95))
                screen.blit(act_lbl, (cx + cartel_w - act_lbl.get_width() - 18, cy + cartel_h - 22))
            else:
                close_lbl = f_small.render("[▲ / ▼] Fermer", True, (130, 125, 115))
                screen.blit(close_lbl, (cx + cartel_w - close_lbl.get_width() - 18, cy + cartel_h - 22))

        except Exception as e:
            log_buffer.warning(f"[art] rendu cartel échoué : {e}")
            try:
                screen.set_clip(None)
            except Exception:
                pass

    def _render_video(self, screen: pygame.Surface, w: int, h: int, fonts: dict) -> None:
        """
        Blitte la frame courante produite par ffmpeg, centrée.

        La Surface n'est reconstruite que lorsque le numéro de séquence du
        player change : les frames arrivent à 15 fps, la boucle de rendu tourne
        à 30, et `frombuffer` + `convert` sur 640x360 n'a pas à être payé deux
        fois par frame. `convert()` passe du RGB24 au format natif de l'écran
        (RGB565 sur le CRT) une bonne fois, au lieu de laisser chaque blit le
        refaire.
        """
        frame, seq = video_player.player.latest_frame()

        if frame is not None and seq != self._video_frame_seq:
            try:
                surf = pygame.image.frombuffer(
                    frame, (video_player.TARGET_W, video_player.TARGET_H), "RGB"
                ).convert()
                self._video_surface = surf
                self._video_frame_seq = seq
                self._video_pos = (
                    (w - video_player.TARGET_W) // 2,
                    (h - video_player.TARGET_H) // 2,
                )
            except Exception as e:
                log_buffer.warning(f"[art] frame vidéo illisible : {e}")

        if self._video_surface is not None:
            screen.blit(self._video_surface, self._video_pos)
            return

        # Pas encore de frame : on dit pourquoi. Un rectangle noir muet laisserait
        # croire à une vidéo noire plutôt qu'à un démarrage ou à une panne.
        self._render_video_message(screen, w, h, fonts)

    def _render_video_message(self, screen: pygame.Surface, w: int, h: int, fonts: dict) -> None:
        """Écran d'attente ou d'erreur, affiché tant qu'aucune frame n'est arrivée."""
        f_m = fonts.get("medium") or pygame.font.Font(None, 22)
        f_s = fonts.get("small") or pygame.font.Font(None, 16)
        name = self._displayed_path.name if self._displayed_path else "vidéo"
        status = video_player.player.status()

        if status == video_player.STATUS_ERROR:
            title, detail, color = (
                f"Lecture impossible — {name}",
                video_player.player.last_error or "cause inconnue",
                (170, 110, 110),
            )
        else:
            title, detail, color = (
                f"▶  {name}",
                "Démarrage de la lecture...",
                (120, 120, 120),
            )

        avail = max(80, w - 2 * MARGIN_LEFT)
        t_surf = f_m.render(_fit_text(title, f_m, avail), True, color)
        d_surf = f_s.render(_fit_text(detail, f_s, avail), True, (130, 130, 130))
        screen.blit(t_surf, ((w - t_surf.get_width()) // 2, h // 2 - 22))
        screen.blit(d_surf, ((w - d_surf.get_width()) // 2, h // 2 + 12))

    def render(self, screen: pygame.Surface, w: int, h: int, bar_h: int, fonts: dict) -> None:
        try:
            self._ensure_loaded()

            if not self.media_paths:
                f_m = fonts.get("medium") or pygame.font.Font(None, 22)
                f_s = fonts.get("small") or pygame.font.Font(None, 16)
                msg1 = f_m.render("Aucune œuvre trouvée dans le dossier 'arts/'", True, (200, 200, 200))
                msg2 = f_s.render("Ajoutez des images ou des vidéos dans le dossier arts du projet.", True, (140, 140, 140))
                screen.blit(msg1, ((w - msg1.get_width()) // 2, h // 2 - 20))
                screen.blit(msg2, ((w - msg2.get_width()) // 2, h // 2 + 15))
                return

            if self.current_kind == "video":
                self._render_video(screen, w, h, fonts)
                if self.show_cartel:
                    self._render_cartel(screen, w, h, fonts)
                return

            if not self.current_surface:
                f_s = fonts.get("small") or pygame.font.Font(None, 16)
                err_msg = f_s.render("Impossible de charger ce média. [◄ / ►] pour changer", True, (200, 100, 100))
                screen.blit(err_msg, ((w - err_msg.get_width()) // 2, h // 2))
                return

            if self._scaled_surface is None or self._scaled_screen_size != (w, h):
                img_w, img_h = self.current_surface.get_size()
                avail_w = w - MARGIN_LEFT - MARGIN_RIGHT
                avail_h = h - MARGIN_TOP - MARGIN_BOTTOM

                if avail_w > 0 and avail_h > 0 and img_w > 0 and img_h > 0:
                    scale = min(avail_w / img_w, avail_h / img_h)
                    new_w = max(1, int(img_w * scale))
                    new_h = max(1, int(img_h * scale))
                    self._scaled_surface = pygame.transform.smoothscale(self.current_surface, (new_w, new_h))
                    self._scaled_pos = (MARGIN_LEFT + (avail_w - new_w) // 2, MARGIN_TOP + (avail_h - new_h) // 2)
                    self._scaled_screen_size = (w, h)

            if self._scaled_surface:
                screen.blit(self._scaled_surface, self._scaled_pos)

            if self.show_cartel:
                self._render_cartel(screen, w, h, fonts)

        except Exception as e:
            log_buffer.warning(f"[art] rendu échoué : {e}")
