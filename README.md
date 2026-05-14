# AirQualityInk

Real-time air quality monitor for Raspberry Pi Zero 2W with a 7-colour eInk display.
Fetches official RSQA data from the Ville de Montréal network, displays the worst-pollutant
colour (WHO 2021 + EU thresholds), and shows a weather forecast — all without any paid API.

---

## Hardware

| Component | Model |
|---|---|
| Single-board computer | Raspberry Pi Zero 2W (512 MB RAM) |
| Display (target) | Pimoroni Inky Impression 4" — 640×400, 7-colour ACeP eInk |
| Display (prototype) | Any HDMI monitor / CRT 720×480i via pygame |
| Optional sensor | DHT22 or SHT31/SHT40 on GPIO (stub ready in `sensor.py`) |

---

## Features

- **Full-screen colour mode** — background reflects the worst pollutant level: green → yellow-green → yellow → orange → red → purple
- **WHO 2021 + EU thresholds** — strictest of the two, for all 6 pollutants (PM2.5, PM10, NO2, O3, SO2, CO)
- **8 RSQA stations** across Montréal island — navigate with ←/→ keys
- **Station bar** — top strip shows all 8 stations' colours simultaneously, ordered from current
- **Weather overlay** — current conditions via Open-Meteo, rain warning if < 2 h
- **Stats overlay** — per-pollutant bars with WHO ratio, toggle with any key or click
- **Zero API keys** — RSQA and Open-Meteo are both free and public
- **Monofett font** — bundled, OFL-licensed

---

## Installation

### Mac (development / prototype)

```bash
git clone https://github.com/Ber-g/eInk-Air-Quality-monitor.git
cd eInk-Air-Quality-monitor
python3 -m venv venv
source venv/bin/activate
pip install requests pygame
python3 main.py
```

### Raspberry Pi Zero 2W

```bash
sudo apt-get install -y python3-pygame python3-pip

git clone https://github.com/Ber-g/eInk-Air-Quality-monitor.git
cd eInk-Air-Quality-monitor
pip3 install -r requirements_raspberry.txt

DISPLAY=:0 AQI_FULLSCREEN=1 python3 main.py
```

---

## Usage

| Input | Action |
|---|---|
| Any key / click | Toggle pollutant stats overlay |
| ← / → | Previous / next station |
| Escape | Quit |

AQI and weather both refresh automatically every 30 minutes.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AQI_FULLSCREEN` | `0` | Set to `1` for fullscreen |
| `AQI_REFRESH` | `1800` | AQI fetch interval in seconds |
| `WEATHER_REFRESH` | `1800` | Weather fetch interval in seconds |

---

## Architecture

```
main.py       — entry point, two daemon threads (AQI + weather), event loop
fetcher.py    — RSQA API, all 8 stations in one request, CO unit conversion, DST fix
aqi.py        — WHO/EU thresholds, LEVEL_COLORS (single source of truth for all colours)
display.py    — pygame renderer: colour mode, stats overlay, station bar
weather.py    — Open-Meteo client, WMO code → Unicode symbol, rain forecast
sensor.py     — local sensor stub (DHT22/SHT31, returns None until wired)
Monofett/     — bundled OFL display font
hardware/     — hardware notes (Inky Impression specs)
```

---

## Data sources

- **Air quality** — [RSQA Ville de Montréal](https://donnees.montreal.ca/dataset/rsqa-indice-qualite-air) — open data, no auth required
- **Weather** — [Open-Meteo](https://open-meteo.com/) — free, no account needed

---

## Roadmap

- [ ] systemd service for autostart on Pi boot
- [ ] Flask web interface — change station from a browser on the local network
- [ ] Inky Impression 4" driver — PIL-based renderer, 7-colour palette
- [ ] Local sensor support — DHT22 / SHT31 (stub ready in `sensor.py`)

---

## License

[MIT](LICENSE) · Font: Monofett by Sorkin Type — [OFL](Monofett/OFL.txt)
