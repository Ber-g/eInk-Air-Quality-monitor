#!/usr/bin/env python3
"""
Lecture vidéo en boucle infinie pour le mode Musée.

Pourquoi un décodage ffmpeg piped dans Pygame, et pas un player système :
la cible (Pi 3 + CRT) n'a AUCUN chemin de sortie exploitable par un player
externe. Trois murs qui s'additionnent :
  1. le CRT est branché sur le connecteur Composite, dont le noyau rapporte
     l'état `unknown` — le code KMS de mpv n'accepte que `connected` et refuse
     l'écran avant même de décoder ;
  2. pas de serveur X (le service tourne en `SDL_VIDEODRIVER=fbcon`), donc
     tout ce qui dépend de X ou Wayland tombe ;
  3. l'app tourne en SDL 1.2 — la seule version qui ait encore `fbcon` — et
     détient `/dev/fb0` ; SDL2, donc ffplay et mpv, n'a plus ce driver.
mpv, ffplay et cvlc ont été testés sur la machine : les trois meurent au
lancement. Un player externe n'est pas « plus lent » ici, il est impossible.

On délègue donc le seul travail coûteux — le décodage — à un process ffmpeg
qui sort du rawvideo RGB24 déjà mis à l'échelle et paddé sur un canevas fixe.
Python ne fait que lire des octets et blitter. Mesuré sur le Pi 3, app en
cours d'exécution, 720p30 source → 1,33× le temps réel à30 fps : la marge
tient. `-re` fait la cadence côté ffmpeg, ce qui évite un thread de timing
en Python et borne la consommation CPU.

Bénéfice secondaire : la vidéo passe par la surface Pygame, donc le cartel se
superpose correctement et la capture d'écran Telegram (`/screen`) la montre.
"""
from __future__ import annotations

import collections
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

# ── Canevas de décodage ──────────────────────────────────────────────────────
# Taille FIXE, quelle que soit la source. `force_original_aspect_ratio=decrease`
# suivi d'un `pad` garantit que ffmpeg sort toujours exactement TARGET_W×TARGET_H
# avec l'aspect préservé et des bandes noires. C'est ce qui permet de se passer
# d'un ffprobe préalable : ni l'orientation, ni la métadonnée de rotation, ni
# le ratio de la source ne peuvent changer la taille des frames qu'on lit.
TARGET_W = 640
TARGET_H = 360
TARGET_FPS = 30
FRAME_BYTES = TARGET_W * TARGET_H * 3  # RGB24

_THUMB_DIRNAME = ".thumbs"
_THUMB_TIMEOUT = 20.0
_STOP_GRACE_SEC = 1.5
_STDERR_TAIL_LINES = 8

# États exposés à l'UI. `starting` existe parce que ffmpeg met ~1 s à sortir sa
# première frame : sans cet état, la page afficherait une erreur pendant ce délai.
STATUS_IDLE = "idle"
STATUS_STARTING = "starting"
STATUS_PLAYING = "playing"
STATUS_ERROR = "error"


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def is_media(path: Path) -> bool:
    return is_video(path) or is_image(path)


def detect_decoder() -> str | None:
    """Chemin du binaire ffmpeg, ou None s'il est absent."""
    return shutil.which("ffmpeg")


def _decode_command(binary: str, path: Path) -> list:
    return [
        binary,
        "-nostdin",
        "-loglevel", "error",
        # -re : ffmpeg lit la source à sa cadence réelle. Sans ça il décoderait
        # à 1,33× et la vidéo jouerait en accéléré, le pipe ne fournissant
        # aucune contre-pression tant que le lecteur suit.
        "-re",
        "-stream_loop", "-1",   # boucle infinie — exigence produit
        "-i", str(path),
        "-an",                  # pas de piste audio : rien ne la jouerait
        "-vf", (
            f"fps={TARGET_FPS},"
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease:flags=fast_bilinear,"
            f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2"
        ),
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "-",
    ]


class VideoPlayer:
    """
    Pilote un unique process ffmpeg produisant des frames RGB24 brutes.

    Un seul média joue à la fois : `play()` tue systématiquement le précédent.
    Le thread de lecture ne touche à aucune API Pygame — il ne manipule que des
    `bytes`. La conversion en `Surface` est faite par l'appelant, dans le thread
    de rendu, parce que Pygame n'est pas sûr hors de ce thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._path: Path | None = None
        self._last_error: str | None = None

        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._stderr_tail: collections.deque = collections.deque(maxlen=_STDERR_TAIL_LINES)

        # Génération : incrémentée à chaque play()/stop(). Un thread de lecture
        # issu d'un média précédent compare la sienne avant d'écrire une frame,
        # ce qui évite qu'un process en cours d'extinction ne pollue l'affichage
        # du média suivant.
        self._generation = 0
        self._frame: bytes | None = None
        self._frame_seq = 0

    # ── État ─────────────────────────────────────────────────────────────────

    @property
    def current_path(self) -> Path | None:
        return self._path

    @property
    def last_error(self) -> str | None:
        """Message d'erreur lisible, enrichi de la dernière ligne de stderr ffmpeg."""
        with self._lock:
            base = self._last_error
            tail = next((l for l in reversed(self._stderr_tail) if l), None)
        if base and tail:
            return f"{base} — {tail}"
        return base or tail

    def is_playing(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def status(self) -> str:
        """État vivant, relu à chaque frame : un `play()` réussi ne prouve rien."""
        with self._lock:
            if self._proc is None:
                return STATUS_ERROR if self._last_error else STATUS_IDLE
            if self._proc.poll() is not None:
                return STATUS_ERROR
            return STATUS_PLAYING if self._frame is not None else STATUS_STARTING

    def latest_frame(self) -> tuple:
        """
        Retourne `(frame_bytes, seq)`. `seq` ne change que lorsqu'une nouvelle
        frame est arrivée : l'appelant s'en sert pour ne reconstruire une
        Surface qu'au besoin, et pas aux 30 fps de la boucle de rendu.
        """
        with self._lock:
            return self._frame, self._frame_seq

    # ── Contrôle ─────────────────────────────────────────────────────────────

    def play(self, path: Path) -> bool:
        """
        Lance le décodage de `path` en boucle infinie.

        Retourne False si ffmpeg est absent ou si le lancement échoue. Un True
        signifie seulement que le process a démarré — la survie se vérifie avec
        `status()`, parce qu'un ffmpeg peut mourir 200 ms plus tard sur un
        fichier corrompu sans que `Popen` ait rien signalé.
        """
        self._terminate(self._detach())

        with self._lock:
            binary = detect_decoder()
            if binary is None:
                self._last_error = "ffmpeg absent — impossible de décoder la vidéo."
                log_buffer.warning(f"[video] {self._last_error}")
                return False

            self._generation += 1
            generation = self._generation
            self._stderr_tail.clear()

            try:
                proc = subprocess.Popen(
                    _decode_command(binary, path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    bufsize=0,
                    # Groupe de process dédié : permet de tuer ffmpeg ET ses
                    # éventuels enfants sans toucher au process Pygame.
                    start_new_session=True,
                )
            except Exception as e:
                self._last_error = str(e)
                log_buffer.warning(f"[video] échec lancement {path.name} : {e}")
                return False

            self._proc = proc
            self._path = path
            self._last_error = None
            self._frame = None
            self._frame_seq += 1

            self._reader = threading.Thread(
                target=self._read_frames, args=(proc, generation),
                name="video-frames", daemon=True,
            )
            self._stderr_reader = threading.Thread(
                target=self._read_stderr, args=(proc, generation),
                name="video-stderr", daemon=True,
            )

        self._reader.start()
        self._stderr_reader.start()
        log_buffer.info(
            f"[video] décodage en boucle : {path.name} "
            f"({TARGET_W}x{TARGET_H} @ {TARGET_FPS} fps)"
        )
        return True

    def stop(self) -> None:
        self._terminate(self._detach())

    def stop_if_playing(self, path: Path) -> None:
        """Arrête la lecture uniquement si c'est bien ce fichier qui joue.

        Utilisé avant une suppression : supprimer un fichier en cours de lecture
        laisserait un process orphelin sur un inode effacé.
        """
        with self._lock:
            if self._path is None:
                return
            try:
                same = self._path.resolve() == path.resolve()
            except OSError:
                same = self._path == path
        if same:
            self._terminate(self._detach())

    # ── Threads de lecture ───────────────────────────────────────────────────

    def _read_frames(self, proc: subprocess.Popen, generation: int) -> None:
        """Lit des frames de taille fixe sur stdout jusqu'à la mort du process."""
        buf = bytearray(FRAME_BYTES)
        view = memoryview(buf)
        stream = proc.stdout
        try:
            while True:
                filled = 0
                while filled < FRAME_BYTES:
                    n = stream.readinto(view[filled:])
                    if not n:
                        return  # EOF : ffmpeg a terminé ou a été tué
                    filled += n
                with self._lock:
                    # Génération périmée : un play() plus récent a pris la main.
                    if generation != self._generation:
                        return
                    self._frame = bytes(buf)
                    self._frame_seq += 1
        except Exception as e:
            with self._lock:
                if generation == self._generation:
                    self._last_error = f"lecture interrompue : {e}"
        finally:
            try:
                stream.close()
            except Exception:
                pass
            code = proc.poll()
            with self._lock:
                if generation != self._generation:
                    return
                # Un arrêt volontaire passe par _detach, qui a déjà incrémenté
                # la génération : si on est encore ici, ffmpeg est mort tout
                # seul — c'est une panne, elle doit être visible.
                if code not in (0, None) and self._last_error is None:
                    self._last_error = f"ffmpeg s'est arrêté (code {code})"
                elif self._frame is None and self._last_error is None:
                    self._last_error = "aucune image produite par ffmpeg"
            if self._last_error:
                log_buffer.warning(f"[video] {self._last_error}")

    def _read_stderr(self, proc: subprocess.Popen, generation: int) -> None:
        """Draine stderr — un pipe plein bloquerait ffmpeg — et garde la fin."""
        try:
            for raw in iter(proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                # ffmpeg cite le chemin absolu ; sur un ecran de 720 px c'est
                # autant de place volee a la cause reelle de l'erreur.
                if self._path is not None:
                    line = line.replace(str(self._path), self._path.name)
                with self._lock:
                    if generation != self._generation:
                        return
                    self._stderr_tail.append(line)
        except Exception:
            pass
        finally:
            try:
                proc.stderr.close()
            except Exception:
                pass

    # ── Privé ────────────────────────────────────────────────────────────────

    def _detach(self) -> subprocess.Popen | None:
        """Oublie le process courant et rend la main dessus, sous verrou."""
        with self._lock:
            proc, self._proc, self._path = self._proc, None, None
            self._frame = None
            self._frame_seq += 1
            self._generation += 1  # invalide les threads du média précédent
            self._last_error = None
            self._reader = None
            self._stderr_reader = None
            return proc

    def _terminate(self, proc: subprocess.Popen | None) -> None:
        """
        Tue le process — impérativement HORS du verrou.

        Attendre la mort de ffmpeg en tenant `_lock` provoquait un interblocage :
        le thread de lecture se bloquait sur ce même verrou, cessait donc de
        vider stdout, et ffmpeg restait coincé dans un `write()` sur un pipe
        plein sans pouvoir traiter son SIGTERM. On attendait alors 2 s pour rien
        — en gelant la boucle de rendu — avant un SIGKILL qui laissait un zombie
        faute de `wait()` derrière lui.
        """
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
        try:
            proc.wait(timeout=_STOP_GRACE_SEC)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        try:
            # Sans ce second wait, le process tué reste un zombie jusqu'à
            # l'arrêt de l'app : SIGKILL ne le fait pas récolter tout seul.
            proc.wait(timeout=_STOP_GRACE_SEC)
        except Exception:
            log_buffer.warning(f"[video] process {proc.pid} non récolté après SIGKILL")


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
                "ffmpeg", "-y", "-nostdin",
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
