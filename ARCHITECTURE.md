# ARCHITECTURE
_Last updated: 2026-10-15 | Version: 2.7.0_

## System Overview

```
                 ┌──────────────┐        ┌─────────────────┐
                 │  RSQA / CKAN │        │   Open-Meteo    │
                 │ (Ville de MTL)│       │    (météo)      │
                 └──────┬───────┘        └────────┬────────┘
                        │ HTTP (polling ~:50)     │ HTTP
                        ▼                         ▼
   ┌──────────────────────────────────────────────────────────┐
   │                        main.py                           │
   │  boucle Pygame 30 fps + threads de fetch + action_queue   │
   └───┬──────────────┬─────────────────┬────────────────┬─────┘
       │              │                 │                │
       ▼              ▼                 ▼                ▼
  ┌─────────┐   ┌───────────┐   ┌──────────────┐  ┌──────────────┐
  │display  │   │ history   │   │remote_server │  │   pages/     │
  │ .py     │   │ .py       │   │ .py (:8088)  │  │ art, debug…  │
  │ pygame  │   │ SQLite    │   │ HTTP JSON    │  └──────┬───────┘
  └────┬────┘   └───────────┘   └──────┬───────┘         │
       │                               │                 ▼
       │                               │        ┌──────────────────┐
       ▼                               │        │  video_player.py │
  ┌──────────┐                         │        │  ffmpeg ─rawvideo│
  │ /dev/fb0 │◄────────────────────────┘        │  → frames RGB24  │
  │ SDL 1.2  │   (screenshot, upload, nav)      └────────┬─────────┘
  │ CRT 720x480 via sortie Composite │                   │
  └──────────┘◄────── blit des frames ────────────────────┘
       ▲
       │  /api/art/upload, /screen
  ┌────┴──────────────────────┐
  │ raspcam_airq_plugin.py    │  ← bot Telegram (hors process)
  └───────────────────────────┘
```

## Stack

| Couche | Choix | Justification |
|---|---|---|
| Matériel | Raspberry Pi 3 Model B (4 cœurs, 1 Go) | disponible ; 4 cœurs suffisent au décodage vidéo logiciel |
| Affichage | CRT 720x480i sur la **sortie Composite** | parti pris esthétique du projet — et contrainte technique majeure (voir plus bas) |
| Écran cible | Pimoroni Inky Impression 4" (640x400, 7 couleurs) | non encore intégré |
| Runtime | Python 3.9.2 système (`/usr/bin/python3`) | fourni par l'OS ; impose `from __future__ import annotations` |
| Rendu | pygame 1.9.6 / **SDL 1.2** | seule pile qui ait encore le driver `fbcon` — voir Known Constraints |
| Données air | RSQA Ville de Montréal (API CKAN) | gratuit, sans token, 8 stations sur l'île |
| Météo | Open-Meteo | gratuit, sans token |
| Cartels | Gemini REST (`gemini-3.5-flash`) | génération des cartels du mode Musée |
| Vidéo | ffmpeg 4.3 en sous-process, pipe rawvideo | seul chemin viable sur cette sortie vidéo |
| Persistance | SQLite (`history.db`) | une ligne par heure et par station |
| Supervision | systemd (`airqink.service`) | redémarrage auto, cgroup mémoire |

## Modules & Services

| Module | Rôle | Frontière publique |
|---|---|---|
| `main.py` | boucle principale 30 fps, threads de fetch, `action_queue` | — |
| `fetcher.py` | API RSQA, `fetch_all()`, CO mg→µg, +1 h DST | `fetch_all()`, `STATIONS` |
| `aqi.py` | seuils WHO 2021 + EU, `LEVEL_COLORS` | `worst_pollutant`, `label_pollutant`, `score_pollutant` |
| `display.py` | rendu pygame, overlays, `NavigationController` | `AQIDisplay`, `capture_screenshot()` |
| `menu.py` | barre de menu, `UIMode`, enregistrement des pages | `NavigationController`, `MenuItem` |
| `pages/base.py` | `BasePage`, `NavAction` | classe de base de toute page |
| `pages/art.py` | mode Musée : playlist images + vidéos, cartel IA | `ArtPage`, `get_current_info()` |
| `pages/debug.py` | état système, journal, refetch/restart/reset | `DebugPage` |
| `video_player.py` | décodage vidéo en boucle via ffmpeg, vignettes | `player`, `is_media()`, `extract_thumbnail()` |
| `history.py` | SQLite, clé composite `(ts, station)` | `save`, `load_history`, `clear` |
| `weather.py` | Open-Meteo, mapping WMO → icône | `fetch_weather()` |
| `map_tile.py` | carte vectorielle OSM, cache JSON | rendu de tuile |
| `log_buffer.py` | ring buffer 200 lignes + fichier tournant 768 Ko | `info()`, `warning()` |
| `remote_server.py` | API HTTP JSON sur `:8088` | endpoints `/api/*` |
| `raspcam_airq_plugin.py` | bot Telegram (process séparé) | commandes `/screen`, envoi de médias |

## Data Models

- **Mesure RSQA** — `(timestamp, station, polluant → µg/m³)`. Le timestamp est **celui de RSQA**, pas celui du Pi : la clé reste idempotente sur redémarrage et sur fetches multiples.
- **`history.db`** — table à clé composite `(ts, station)` : une ligne par heure et par station.
- **Média du Musée** — un fichier dans `arts/` + un `.json` voisin (le cartel, mis en cache) + une vignette dans `arts/.thumbs/`.
- **Cartel** — `{titre, artiste, annee, matiere, ton, reconnue, contexte_oeuvre, contexte_artiste}`, plus depuis la v2.6 :
  - `source` ∈ `ia_en_attente` (amorce posée à l'upload, Gemini doit compléter) · `ia` · `manuel` (jamais envoyé à Gemini) ;
  - `titre_verrouille` — l'IA peut tout réécrire sauf le titre.
  L'amorce est écrite **sur disque** dès l'upload, et non gardée en mémoire : si l'app tombe pendant que Gemini travaille, le titre donné par l'expéditeur serait perdu.
- **Frame vidéo** — tampon RGB24 de taille **fixe** 640×360×3 = 691 200 octets, accompagné d'un numéro de séquence monotone. À 30 fps cela représente **20,7 Mo/s** dans le pipe.

## Dependencies

| Nom | Version | Rôle | Risque |
|---|---|---|---|
| pygame | 1.9.6 (système, SDL 1.2) | rendu | **élevé** — version figée, une mise à jour vers pygame 2 casserait l'affichage (voir Known Constraints) |
| requests | 2.31.0 | HTTP | faible |
| Pillow | 10.0.1 | images | faible |
| python-dotenv | 1.0.0 | `.env` | faible |
| ffmpeg / ffprobe | 4.3.9 (apt) | décodage vidéo + vignettes | **moyen** — dépendance système ; son absence désactive la vidéo avec un message explicite |
| API RSQA | — | données air | moyen — service public, pas de SLA |
| Open-Meteo | — | météo | faible |
| Gemini REST | `gemini-3.5-flash` | cartels | moyen — modèles dépréciés régulièrement, d'où la liste `FALLBACK_MODELS` |

`mpv`, `vlc` et `ffplay` sont installés sur le Pi mais **ne sont plus utilisés** (voir le Change Log du 2026-10-14).

## Integration Map

| Appelant | Appelé | Protocole |
|---|---|---|
| `main.py` | RSQA, Open-Meteo | HTTPS |
| `pages/art.py` | Gemini | HTTPS REST |
| `pages/art.py` | `video_player` | appel direct + pipe vers ffmpeg |
| bot Telegram | `remote_server` | HTTP JSON sur `127.0.0.1:8088` |
| `remote_server` | boucle principale | `action_queue` (`queue.Queue`, réponse synchrone, timeout 3 s) |
| bot musée | `/api/art/upload` | en-têtes `X-Art-Title`, `X-No-AI`, `X-On-Conflict` (textes percent-encodés) |
| bot musée | `/api/art/cartel_set` | cartel saisi à la main, JSON |
| bot musée | `/api/art/rename` | renomme le **fichier** (média + cartel + vignette), sans toucher au titre ; 409 si le nom est pris |

## Known Constraints & Trade-offs

1. **Aucun player vidéo externe ne peut s'afficher sur cette machine.** Trois murs cumulés : le CRT est sur le connecteur **Composite**, dont le noyau rapporte l'état `unknown` et que le code KMS de mpv refuse ; il n'y a pas de serveur X ; et l'app tourne en SDL 1.2 — seule version qui ait encore `fbcon` — en détenant `/dev/fb0`. mpv, ffplay et cvlc ont été testés : les trois meurent au lancement. D'où le décodage par pipe ffmpeg.
2. **pygame est épinglé de fait à la 1.9.6 système.** `requirements.txt` déclare `pygame==2.6.1`, mais le service lance `/usr/bin/python3`, donc la 1.9.6. Installer pygame 2 au niveau système empêcherait l'app de démarrer : SDL 2 n'a pas de driver `fbcon`. ⚠️ À documenter avant toute migration.
3. **`MemoryMax=500M`** sur le cgroup du service, partagé avec ffmpeg (~48 Mo en lecture) ; l'app seule tient sous 80 Mo.
4. **La vidéo est plafonnée à 640×360 @ 30 fps**, canevas fixe avec bandes noires. Le format fixe évite tout `ffprobe` préalable : ni l'orientation, ni la rotation, ni le ratio de la source ne peuvent changer la taille des frames lues. 30 fps aligne la cadence de décodage sur celle de la boucle de rendu (`clock.tick(30)`), ce qui supprime le battement d'une source 15 fps affichée dans une boucle à 30.
5. **Le décodage à 30 fps sature la machine.** Mesuré sur le Pi 3 : ffmpeg ~1,44 cœur, l'app passe de 35 % à 49 % d'un cœur, load ≈ 4,0 sur 4 cœurs. Le débit livré est de **29,3 fps sur une source 480p** et de **26,9 fps sur une mire 720p** (pire cas : ~10 % de frames perdues). Repasser `TARGET_FPS` à 15 rend 1,4 cœur si la marge devient nécessaire.
6. **Alimentation USB 1,2 A sous-dimensionnée** — `vcgencmd get_throttled` renvoie `0x50005` (sous-tension et throttling, actifs et historiques) **y compris au repos** : c'est un état préexistant du montage, pas une conséquence de la vidéo. La température reste à 62 °C, donc c'est bien l'alimentation et non le refroidissement. Une alim 2,5 A est le vrai correctif ; en attendant, la marge réelle est plus mince que ne le suggèrent les chiffres CPU.
7. Ne pas faire d'`apt upgrade` pendant que l'app tourne (cf. contrainte d'alimentation ci-dessus).
8. `arts/` n'est jamais synchronisé : le musée du Pi se remplit par Telegram, celui du Mac sert aux tests.

## Security Posture

- **Secrets** : `OPENWEATHER_API_KEY`, `GEMINI_API_KEY` dans `.env`, hors du dépôt. Aucun secret en dur.
- **API `remote_server`** : **sans authentification**. Écoute sur `127.0.0.1:8088` (`DEFAULT_HOST`) ; toute exposition sur le LAN donnerait à n'importe qui l'upload de fichiers, la suppression de médias et la capture d'écran. ⚠️ Voir `QA.md`.
- **Upload** : extension déduite des **octets magiques**, pas du nom de fichier ; taille plafonnée par `MAX_UPLOAD_BYTES`.
- **Sous-process** : ffmpeg est lancé en liste d'arguments (jamais via un shell), dans sa propre session, avec `stdin` fermé.
- **Surface d'entrée** : API RSQA, Open-Meteo, Gemini, fichiers déposés par Telegram, endpoints HTTP locaux.

---
## CHANGE LOG

### 2026-10-15 — v2.7 : renommer une œuvre

**Changed:** `pages/art.py` — `rename_media()` déplace le média, son cartel et sa vignette. **Le cartel est déplacé, pas réécrit** : renommer un fichier ne retitre pas l'œuvre. `_ascii_stem()` y est dupliqué depuis `remote_server` à dessein : les deux chemins doivent produire le même nom, sinon renommer donnerait un nom qu'un upload du même titre n'aurait jamais produit. Nouvelle route `POST /api/art/rename` et action `art_rename`.

**Reason:** un fichier horodaté illisible (`video_telegram_20261014_222047.mp4`) ne pouvait être corrigé qu'en supprimant l'œuvre et en la renvoyant — ce qui perdait son cartel.

Renommer et retitrer sont deux gestes distincts : le nom de fichier sert à désigner l'œuvre dans les commandes, le titre est ce que le visiteur lit. `set_cartel()` s'occupe du titre.

**Impact:**
- Le média est déplacé en premier : si ça échoue, rien n'a bougé ; si ça réussit, les fichiers dérivés suivent ou se régénèrent — ils sont reconstructibles, le média non.
- Le cartel renommé reste plus récent que le média, donc le cache n'est pas jugé périmé.
- Une vidéo en cours de lecture est arrêtée avant le renommage puis relancée : un lecteur tenant l'ancien inode y aurait survécu.
- Un nom déjà pris renvoie **409**, comme l'upload — l'appelant traite les deux cas pareil.

**Open questions:** nom de fichier et titre peuvent diverger — c'est assumé, et c'est tout l'intérêt.


### 2026-10-14 — v2.6 : l'œuvre peut être nommée, et soustraite à l'IA

**Changed:**
- `remote_server.py` — l'upload accepte `X-Art-Title` (titre de l'œuvre), `X-No-AI` et `X-On-Conflict`. Les en-têtes porteurs de texte sont **percent-décodés** : un en-tête HTTP ne transporte que du latin-1, « Nuit étoilée » y arrivait mutilé — le bug existait déjà sur `X-Filename` et passait inaperçu faute d'appelant. Nouvelle route `POST /api/art/cartel_set`.
- `pages/art.py` — champs `source` et `titre_verrouille` dans le cartel ; `set_cartel()` ; `_resolve_media()` factorise le garde-fou de traversée de chemin, désormais partagé avec `delete_media()`. Les abandons silencieux de génération de cartel sont journalisés.
- `main.py` — action `art_cartel_set`.

**Reason:** le musée nommait les œuvres par horodatage, écrasait en silence les homonymes derrière un suffixe `_1`, et envoyait tout média à Gemini sans échappatoire.

**Impact:**
- Un nom déjà pris est désormais **refusé** (HTTP 409 + nom et rang de l'existante) quand un titre est fourni. Sans titre, l'ancien suffixage est conservé — les appelants historiques (`raspcam_airq_plugin.py`) ne changent pas de comportement.
- Un `replace` écrase le média sans effacer explicitement son `.json` ni sa vignette : leur validité se juge déjà sur la date du média, qui vient de changer. Ils se régénèrent d'eux-mêmes.
- Les noms de fichiers sont repliés en **ASCII** (« Nuit étoilée » → `Nuit_etoilee.jpg`) ; le titre affiché garde ses accents. Un nom sans accent traverse sans dommage les en-têtes, les URL et les commandes Telegram.
- ⚠️ Contrat partagé avec le dépôt RaspCam (bot musée). Rien ne signale une divergence de version.

**Open questions:**
- Le verrou de titre vit dans le `.json` : l'effacer à la main rend le titre à l'IA au prochain passage.
- `/api/art/select` ne re-scanne toujours pas `arts/` (`BUG-004`) — hors périmètre.


### 2026-10-14 — Cadence vidéo portée de 15 à 30 fps
**Changed:** `video_player.py` — `TARGET_FPS` 15 → 30. Aucune autre modification : le canevas reste 640×360 et le filtre est inchangé.

**Reason:** décision de l'utilisateur. La cadence s'aligne désormais sur la boucle de rendu (`clock.tick(30)`), ce qui supprime le battement d'une source 15 fps échantillonnée par une boucle à 30 — une frame sur deux y était affichée deux fois.

**Impact:** mesuré sur le Pi 3, app en marche :

| Indicateur | 15 fps | 30 fps |
|---|---|---|
| ffmpeg | ~0,60 cœur | **~1,44 cœur** |
| App (rendu : `frombuffer` + `convert` + blit) | 35 % d'un cœur | **49 %** |
| Load (4 cœurs) | ~1,6 | **~4,0** |
| Débit livré — source 480p | 14,9 / 15 | **29,3 / 30** |
| Débit livré — mire 720p (pire cas) | 14,9 / 15 | **26,9 / 30** |
| Débit dans le pipe | 10,4 Mo/s | **20,7 Mo/s** |

- Sur une source 720p très détaillée, ffmpeg perd ~10 % des frames : la lecture reste fluide mais n'atteint pas tout à fait 30 fps. Sur une source de téléphone ordinaire, la cible est tenue.
- La machine passe de « confortable » à « saturée » : load ≈ 4,0 sur 4 cœurs pendant la lecture. Le mode Musée est une page au premier plan, pendant laquelle rien d'autre n'est critique — les fetches RSQA sont horaires et tolèrent la latence.
- ⚠️ `vcgencmd get_throttled` = `0x50005` : sous-tension et throttling actifs. **Vérifié au repos, vidéo arrêtée : flags identiques** — l'état est préexistant (alim 1,2 A), pas causé par ce changement. Mais il réduit la marge réelle sous charge.

**Open questions:**
- Passer à une alimentation 2,5 A ? C'est le seul vrai correctif à la sous-tension, et il rendrait les 30 fps confortables au lieu de justes.
- Faut-il retomber automatiquement à 15 fps quand ffmpeg n'arrive pas à suivre, plutôt que de laisser la cadence se dégrader silencieusement ? Non implémenté.


### 2026-10-14 — Lecture vidéo : abandon du player externe au profit d'un pipe ffmpeg
**Changed:**
- `video_player.py` réécrit. Le lancement de mpv/ffplay/cvlc est remplacé par un process `ffmpeg … -re -stream_loop -1 … -f rawvideo -` dont les frames RGB24 sont lues par un thread et blittées par la boucle de rendu. Nouvelles API : `status()`, `latest_frame()`, `detect_decoder()` ; `_PLAYERS`/`detect_player()` supprimés.
- `pages/art.py` : `_render_video_placeholder` → `_render_video` (blit réel) + `_render_video_message` (attente/erreur). Le booléen `_video_ok` est supprimé au profit de `player.status()`, relu à chaque frame. Ajout de `_fit_text()` pour que les erreurs ffmpeg ne débordent plus de l'écran.
- `remote_server` (via `get_current_info`) : nouveau champ `video_status` ; `video_playing` et `video_error` dérivent désormais de l'état vivant.
- `systemd/airqink.service` : `MemoryMax` 200M → 500M.

**Reason:** la vidéo n'avait **jamais** fonctionné sur la cible. mpv était lancé, mourait aussitôt, et `play()` renvoyait `True` parce que `Popen` avait réussi — l'écran affichait « Lecture en boucle » sur une panne totale. Cause racine : sortie Composite au statut `unknown`, pas de serveur X, `/dev/fb0` détenu par SDL 1.2.

**Impact:**
- La vidéo passe par la surface pygame : le cartel se superpose correctement et `/api/screenshot` (donc `/screen` sur Telegram) la montre enfin.
- Coût CPU mesuré sur le Pi 3, app en marche : ~60 % d'un cœur sur une mire 720p (pire cas), charge système ~1,6 sur 4 cœurs. *(Chiffres de la version 15 fps — voir l'entrée 2.5.2 pour les valeurs à 30 fps.)*
- `mpv` et `vlc` deviennent des dépendances mortes — désinstallables.
- Les clients de l'API voient un champ `video_status` supplémentaire (ajout rétrocompatible).

**Open questions:**
- Faut-il désinstaller `mpv`/`vlc` du Pi pour alléger la carte SD ?
- L'adaptation Inky Impression (15 s de rafraîchissement) rend la vidéo inapplicable : à trancher par `@cpo` lors du portage.

### 2026-10-14 — ARCHITECTURE.md initialisé
**Changed:** scaffold du fichier à partir de l'état réel du dépôt en v2.5.
**Reason:** le protocole impose un ARCHITECTURE.md ; il n'existait pas.
**Impact:** aucun changement de code.
**Open questions:** `SPEC.md` et `OPS.md` restent à scaffolder par `@cpo`.
