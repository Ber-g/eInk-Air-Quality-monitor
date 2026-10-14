#!/usr/bin/env python3
"""
Lecture vidéo en boucle infinie pour le mode Musée.

Pourquoi un process externe et pas un décodage Python :
Pygame ne décode pas la vidéo. Les alternatives in-process (OpenCV, imageio)
décodent en espace utilisateur — sur un Pi Zero 2W (512 MB, pas de VPU
exploitable depuis Python) une 1080p chute sous 5 fps et sature le CPU déjà
partagé avec la boucle de rendu 30 fps et les threads de fetch.

On délègue donc à un player système (mpv / ffplay / cvlc) lancé en plein écran
par-dessus la fenêtre Pygame, en boucle infinie, et tué au changement de média.
Coût : une dépendance système optionnelle. Bénéfice : décodage matériel, zéro
charge sur la boucle de rendu, et un fallback lisible si le binaire est absent.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
from pathlib import Path

import log_buffer

# ── Formats reconnus ─────────────────────────────────────────────────────────
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}

# ── Players supportés, par ordre de préférence ───────────────────────────────
# `loop_args` doit produire une boucle INFINIE : c'est l'exigence produit.
_PLAYERS: list[tuple[str, list[str]]] = [
    # mpv : le plus léger et le seul à exposer --loop-file=inf de façon fiable
    ("mpv", [
        "--loop-file=inf", "--fullscreen", "--no-osc", "--no-terminal",
        "--really-quiet", "--no-input-default-bindings", "--cursor-autohide=always",
    ]),
    # ffplay : déjà présent si ffmpeg est installé (il l'est pour les vignettes)
    ("ffplay", ["-loop", "0", "-fs", "-loglevel", "quiet", "-autoexit"]),
    # cvlc : dernier recours, plus lourd en RAM
    ("cvlc", ["--loop", "--fullscreen", "--no-video-title-show", "--quiet"]),
]

_THUMB_DIRNAME = ".thumbs"
_THUMB_TIMEOUT = 20.0
_STOP_GRACE_SEC = 2.0


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def is_media(path: Path) -> bool:
    return is_video(path) or is_image(path)


def detect_player() -> tuple[str, list[str]] | None:
    """Retourne (binaire, arguments de boucle) du premier player disponible."""
    for name, args in _PLAYERS:
        binary = shutil.which(name)
        if binary:
            return binary, args
    return None


class VideoPlayer:
    """
    Pilote un unique process de lecture vidéo en boucle.

    Un seul média joue à la fois : `play()` tue systématiquement le précédent.
    Toutes les méthodes sont sûres à appeler depuis le thread Pygame ; le verrou
    protège contre un `stop()` concurrent venant d'une suppression via l'API.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._path: Path | None = None
        self._last_error: str | None = None

    # ── État ─────────────────────────────────────────────────────────────────

    @property
    def current_path(self) -> Path | None:
        return self._path

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def is_playing(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    # ── Contrôle ─────────────────────────────────────────────────────────────

    def play(self, path: Path) -> bool:
        """Lance `path` en boucle infinie. Retourne False si aucun player n'est installé."""
        with self._lock:
            self._stop_locked()

            player = detect_player()
            if player is None:
                self._last_error = (
                    "Aucun lecteur vidéo installé (mpv, ffplay ou vlc requis)."
                )
                log_buffer.warning(f"[video] {self._last_error}")
                return False

            binary, loop_args = player
            cmd = [binary, *loop_args, str(path)]
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    # Groupe de process dédié : permet de tuer le player ET ses
                    # éventuels enfants sans toucher au process Pygame.
                    start_new_session=True,
                )
                self._path = path
                self._last_error = None
                log_buffer.info(f"[video] lecture en boucle : {path.name} ({Path(binary).name})")
                return True
            except Exception as e:
                self._proc = None
                self._path = None
                self._last_error = str(e)
                log_buffer.warning(f"[video] échec lancement {path.name} : {e}")
                return False

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def stop_if_playing(self, path: Path) -> None:
        """Arrête la lecture uniquement si c'est bien ce fichier qui joue.

        Utilisé avant une suppression : supprimer un fichier en cours de lecture
        laisserait un process orphelin sur un inode effacé.
        """
        with self._lock:
            if self._path is not None and self._path.resolve() == path.resolve():
                self._stop_locked()

    # ── Privé ────────────────────────────────────────────────────────────────

    def _stop_locked(self) -> None:
        proc, self._proc, self._path = self._proc, None, None
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
        try:
            proc.wait(timeout=_STOP_GRACE_SEC)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()


# Instance unique partagée par ArtPage et l'API distante.
player = VideoPlayer()


# ── Vignettes ────────────────────────────────────────────────────────────────

def thumbnail_path(video_path: Path) -> Path:
    return video_path.parent / _THUMB_DIRNAME / f"{video_path.stem}.jpg"


def extract_thumbnail(video_path: Path) -> Path | None:
    """
    Extrait une image fixe de la vidéo, pour que l'IA puisse générer un cartel.

    Appelé depuis un thread de fond uniquement (ffmpeg bloque plusieurs secondes).
    Retourne None si ffmpeg est absent ou si l'extraction échoue — l'appelant
    doit alors se rabattre sur un cartel basé sur le nom de fichier.
    """
    out = thumbnail_path(video_path)
    try:
        if out.exists() and out.stat().st_mtime >= video_path.stat().st_mtime:
            return out
    except OSError:
        pass

    if shutil.which("ffmpeg") is None:
        log_buffer.warning("[video] ffmpeg absent — pas de vignette pour le cartel")
        return None

    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                # -ss avant -i : seek rapide, on vise 1s pour éviter un fondu au noir
                "-ss", "1",
                "-i", str(video_path),
                "-frames:v", "1",
                "-vf", "scale=640:-2",
                str(out),
            ],
            check=True,
            capture_output=True,
            timeout=_THUMB_TIMEOUT,
        )
        return out if out.exists() else None
    except Exception as e:
        log_buffer.warning(f"[video] vignette échouée pour {video_path.name} : {e}")
        return None
