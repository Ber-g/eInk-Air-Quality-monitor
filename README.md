# AirQualityInk — v2.4

Moniteur de qualité de l'air en temps réel pour Raspberry Pi Zero 2W.
Affiche les données officielles RSQA de la Ville de Montréal, la météo, une horloge analogique et une carte vectorielle de la ville — sans aucune clé API payante.

---

## Matériel

| Composant | Modèle |
|---|---|
| Ordinateur | Raspberry Pi Zero 2W (512 MB RAM) |
| Écran (cible) | Pimoroni Inky Impression 4" — 640×400, 7 couleurs ACeP eInk |
| Écran (prototype) | Tout moniteur HDMI / CRT 720×480i via pygame |

---

## Utilisation

### Mode principal

| Entrée | Action |
|---|---|
| N'importe quelle touche / clic | Basculer vers la vue détails |
| ← / → | Station précédente / suivante |
| Tab | Ouvrir le menu |
| Échap | Quitter |

### Menu (style Amiga / Minitel)

| Entrée | Action |
|---|---|
| ← / → ou Tab | Naviguer entre les entrées du menu |
| Entrée | Ouvrir la page sélectionnée (animation double-blink) |
| Échap | Fermer le menu |

### Dans une page

| Entrée | Action |
|---|---|
| Tab | Passer directement à la page suivante |
| Échap | Retour au menu |
| **Page Debug** — `[R]` | Forcer un refetch immédiat |
| **Page Debug** — `[Q]` | Redémarrer l'application (`os.execv`) |

---

## Sources de données

### Qualité de l'air — RSQA (Ville de Montréal)

**Choix** : [RSQA — données ouvertes Montréal](https://donnees.montreal.ca/dataset/rsqa-indice-qualite-air)

Le RSQA (Réseau de surveillance de la qualité de l'air) est le réseau officiel de la Ville de Montréal. Il exploite 8 stations permanentes réparties sur l'île, mesurant PM2.5, PM10, NO2, O3, SO2 et CO en continu, avec une nouvelle lecture publiée chaque heure.

**Pourquoi RSQA et pas autre chose :**

| Source | Raison d'écart |
|---|---|
| MELCCFP (réseau provincial) | Les stations du MELCCFP dans la région montréalaise *sont* les stations RSQA — même source, données identiques |
| OpenAQ | Agrégateur qui aspire RSQA — même données, couche supplémentaire inutile |
| PurpleAir | Capteurs communautaires low-cost présents à Montréal, mais aucun dans le quartier ciblé (Villeray) ; qualité de mesure inférieure aux capteurs officiels |

**Accès** : API CKAN publique, aucun token requis.  
`GET https://donnees.montreal.ca/api/3/action/datastore_search?resource_id=f4eca3bf-...&limit=500&sort=_id desc`

**Particularités techniques :**
- Le CO est publié en **mg/m³** dans l'API, tous les autres polluants en **µg/m³** — conversion ×1000 appliquée dans `fetcher.py`
- Les timestamps RSQA sont en **HNE (UTC-5)** toute l'année. En été (EDT), on ajoute +1h pour obtenir l'heure locale
- Un seul appel API récupère toutes les stations en une fois (filtre `limit=500`)
- Fenêtre de polling : les données sont publiées vers **:50–:00** — le fetch se fait toutes les minutes dans cette fenêtre, puis attend la prochaine heure sinon

**Stations (8 sur l'île) :**

| Clé | Nom | Coordonnées |
|---|---|---|
| `ahuntsic` | Ahuntsic | 45.5481, -73.6639 |
| `rosemont` | Rosemont | 45.5408, -73.5728 |
| `centre_sud` | Centre-Sud | 45.5174, -73.5502 |
| `ndg` | NDG / Décarie | 45.4783, -73.6340 |
| `st_laurent` | Saint-Laurent | 45.4974, -73.7358 |
| `laval_n` | Nord (Chateauneuf) | 45.6200, -73.7600 |
| `ste_marie` | Sainte-Marie | 45.5050, -73.5580 |
| `verdun` | Verdun / Wilfrid | 45.4588, -73.5649 |

Les stations sans données à l'instant du fetch sont automatiquement exclues de la navigation ←/→.

---

### Météo — Open-Meteo

**Choix** : [Open-Meteo](https://open-meteo.com/) — API gratuite, sans compte, sans clé.

Point de référence météo : **8464 Henri-Julien, Montréal** (45.5427, -73.6356) — au cœur de Villeray.

**Données récupérées :**
- Température actuelle (°C)
- Code météo WMO (0–99)
- `is_day` — pour choisir l'icône jour ou nuit
- Précipitations horaires sur 48h — pour calculer `rain_at` (prochain créneau avec ≥ 0.2 mm/h)

**Rafraîchissement** : toutes les 5 minutes (configurable via `WEATHER_REFRESH`).

**Icônes météo** : police [Weather Icons](https://erikflowers.github.io/weather-icons/) d'Erik Flowers (TTF, codepoints PUA `0xf000+`). Chaque code WMO est mappé vers une paire (jour, nuit). Fallback Unicode (☀ ☁ ☔ ❄) si la police TTF est absente. Les codepoints sont écrits `chr(0xf00d)` dans le source pour éviter les problèmes d'encodage PUA.

---

### Carte vectorielle — OpenStreetMap via Overpass API

**Choix** : données OpenStreetMap, interrogées via [Overpass API](https://overpass-api.de/).

**Pourquoi vectoriel et pas raster :**
- Pas de clé API ni de quota de tuiles
- Rendu monochromatique natif (suit la couleur du texte — blanc sur fond sombre, noir sur fond clair)
- Pas de dépendance réseau après le premier chargement

**Ce qui est téléchargé :**
- Routes : `highway ~ motorway|trunk|primary|secondary`
- Eau : `natural=water` + `waterway ~ river|canal`
- Bounding box : `(45.43, -73.80, 45.65, -73.52)` — couvre toutes les stations + marges

**Performance Pi Zero :**  
Les ~16 000 segments de route sont pré-baked en une `pygame.Surface(SRCALPHA)` une seule fois au chargement. Chaque frame = 1 `blit()` au lieu de 16 000 `aalines()`.

**Projection :**  
Projection équirectangulaire corrigée pour la latitude. À 45.54°N, `cos(45.54°) ≈ 0.700` — 1° de longitude représente 70 % de la distance physique d'un degré de latitude. Le `_REF_W` est calculé automatiquement :  
`_REF_W = int(Δlon × cos(lat_centre) / Δlat × _REF_H)` → **196 × 220 px**  
Sans cette correction, la carte serait étirée de 40 % horizontalement.

**Comportement de la carte :**
- Centrée sur le milieu entre le point météo et la station courante
- Auto-zoom si les deux points ne tiennent pas dans la fenêtre (avec 12 px de padding pour ne pas clipper les cercles)
- Surface mise à l'échelle cachée entre deux changements de station (pas de re-scale à 30 fps)
- Aucun fond, aucun cadre — s'adapte au contraste (noir ou blanc)
- Fenêtre de visualisation responsive : se réduit verticalement si le contenu au-dessus l'exige, sans déformer la carte (`set_clip`)
- Cache disque (`map_data.json`) — détection automatique de corruption avec re-fetch depuis Overpass

---

## Architecture logicielle

```
main.py          — point d'entrée, boucle d'événements pygame + 2 threads daemon
fetcher.py       — client RSQA, conversion CO, correction DST
aqi.py           — seuils OMS 2021 + UE, couleurs AQI (source de vérité)
display.py       — rendu pygame : mode couleur, mode détails, écran de chargement
weather.py       — client Open-Meteo, mapping WMO → icône jour/nuit
history.py       — persistance SQLite, 48 entrées max (24h à 30 min d'intervalle)
map_tile.py      — carte vectorielle OSM, baking, cache, projection
log_buffer.py    — ring buffer 200 lignes + RotatingFileHandler (768 KB max sur SD)
menu.py          — NavigationController, UIMode, barre de menu, animation blink
pages/base.py    — BasePage + enum NavAction (protocole commun à toutes les pages)
pages/debug.py   — page Debug : état système, journal, refetch, redémarrage
pages/settings.py— page Paramètres (placeholder)
Monofett/        — police OFL pour le label de qualité (mode couleur)
systemd/         — service et scripts d'installation pour Pi
```

### Threads

```
Thread principal  → boucle pygame (render à 30 fps)
_fetch_loop       → fetch RSQA immédiat au démarrage, puis polling horaire
_weather_loop     → fetch Open-Meteo toutes les 5 min
map_tile._fetch   → fetch Overpass en arrière-plan au démarrage (une fois)
```

### Fetch en arrière-plan + fallback stale data

Quand on change de station (ou qu'un refetch est déclenché), `display.start_loading()` est appelé à la place de `data = None`. Le dernier jeu de données valide est conservé dans `_stale_data`. Si le fetch réseau met plus de **3 secondes**, les données précédentes sont réaffichées automatiquement et un spinner animé `· / ·` apparaît en bas à droite pendant que le fetch continue en arrière-plan.

### Menu Amiga / Minitel

Architecture de navigation à profondeur 1 : `UIMode.NORMAL` → `MENU_BAR` → `PAGE`. Ajouter une nouvelle page = créer une sous-classe de `BasePage` + une ligne `MenuItem` dans `menu.py`, rien d'autre ne change.

### Journal (`log_buffer`)

Tous les modules utilisent `log_buffer.info/warning/error()` au lieu de `print()`. Les 200 dernières lignes sont disponibles en mémoire (ring buffer) et affichées dans la page Debug. Un `RotatingFileHandler` écrit en parallèle dans `logs/app.log` (256 KB × 3 fichiers = 768 KB max, compatible carte SD).

### Historique

SQLite local (`history.db`). Plafonné à **48 entrées** (= exactement 24h à un refresh toutes les 30 min). Dédupliqué par `timestamp` de données — changer de station dans la même heure n'ajoute pas de barre parasite. Affiché sous forme de barres colorées en bas à gauche de la vue détails.

---

## Interface utilisateur

### Mode couleur

L'écran entier est rempli de la couleur correspondant au pire polluant actuel.

**Palette AQI (seuils OMS 2021 / UE, le plus strict des deux) :**

| Couleur | Signification |
|---|---|
| Vert `(0, 210, 0)` | Bon |
| Jaune-vert | Acceptable |
| Jaune | Modéré |
| Orange | Mauvais pour groupes sensibles |
| Rouge | Mauvais |
| Violet | Très mauvais |

**Éléments affichés :**
- **Label de qualité** en police Monofett (grande, centre)
- **Polluant + valeur** sous le label
- **Ratio OMS** (ex. "3× OMS") si applicable
- **Barre de stations** en haut — un rectangle coloré par station, ordonnées depuis la courante
- **Météo** en haut à gauche — icône (Weather Icons TTF) + température + alerte pluie si < 2h
- **Horloge analogique** en haut à droite — même hauteur que le bloc météo
- **Station + âge des données** en bas à droite
- **Flèche de tendance** ↗ ↘ → en bas à gauche (comparaison avec le fetch précédent)

Tout le texte est **noir pur** ou **blanc pur** selon la luminance du fond — pas de gris, pas de transparence (illisible sur CRT).

### Mode détails (overlay)

Overlay blanc semi-transparent sur le fond coloré.

**En-tête compact :**
- Ligne 1 : nom de la station (gauche) + heure HH:MM (droite)
- Ligne 2 : grande icône météo + température + date du dernier relevé en italique | message pluie ou *"Pas de pluie prévue — belle journée à Montréal"*
- Séparateur

**Corps :** une rangée par polluant actif — nom + valeur (gauche), label (droite), barre de progression colorée.

**Pied de page :**
- Graphique d'historique 24h (barres colorées, bas gauche)
- Carte vectorielle (bas droite)

### Écran de chargement

Pendant le fetch initial, les 15 icônes météo du jeu Weather Icons défilent horizontalement en continu à 2 px/frame. Repli sur "Chargement…" si la police TTF est absente.

Un fond vert apparaît dès l'initialisation de pygame (~5s après le boot), avant même le chargement des modules lourds — évite 25s d'écran noir.

### Menu Debug

La page Debug affiche 4 cartes d'état côte à côte (station courante, âge des données, heure du prochain fetch, score AQI), suivies du journal des 200 dernières lignes de log. Le prochain fetch est calculé comme l'heure exacte à `:50` de l'heure courante ou suivante.

---

## Choix de polices

| Usage | Police | Raison |
|---|---|---|
| Label de qualité | **Monofett** (bundlée, OFL) | Esthétique display, lisible à grande taille |
| Icônes météo | **Weather Icons** (erikflowers, TTF) | Seule fonte avec tous les symboles météo WMO jour/nuit, license OFL |
| Tout le reste | **DejaVu Sans** (Pi) / **Arial Unicode** (Mac) | Large couverture Unicode, disponible par défaut |
| Date dans détails | Variante **italique** de la fonte système | Distingue visuellement le timestamp des données |

---

## Configuration

| Variable | Défaut | Description |
|---|---|---|
| `AQI_FULLSCREEN` | `0` | `1` pour plein écran |
| `AQI_REFRESH` | `1800` | Intervalle fetch AQI (secondes) |
| `WEATHER_REFRESH` | `300` | Intervalle fetch météo (secondes) |

---

## Installation

### Mac (développement)

```bash
git clone https://github.com/Ber-g/eInk-Air-Quality-monitor.git
cd eInk-Air-Quality-monitor
python3 -m venv venv && source venv/bin/activate
pip install requests pygame
# Télécharger weather-icons.ttf depuis erikflowers/weather-icons
python3 main.py
```

### Raspberry Pi Zero 2W

```bash
bash systemd/install.sh   # installe dépendances + service systemd + police Weather Icons
```

Le service démarre automatiquement au boot et se relance en cas d'erreur. L'écran affiche un fond vert dès le chargement de pygame (~5–8s), puis l'animation de chargement pendant le fetch des données (~10–15s supplémentaires).

---

## Licence

[MIT](LICENSE) · Monofett : Sorkin Type — [OFL](Monofett/OFL.txt) · Weather Icons : Erik Flowers — OFL
