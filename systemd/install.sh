#!/bin/bash
# À lancer depuis ~/Documents/AirQ/systemd/ sur le Pi
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

sudo cp airqink.service /etc/systemd/system/
sudo systemctl daemon-reload

sudo cp mode-airqink mode-desktop /usr/local/bin/
sudo chmod +x /usr/local/bin/mode-airqink /usr/local/bin/mode-desktop

# S'assurer que l'utilisateur est dans le groupe video (pour fbcon)
sudo usermod -aG video beranger

# Police Weather Icons (Erik Flowers)
FONT_PATH="$PROJECT_DIR/weather-icons.ttf"
FONT_URL="https://raw.githubusercontent.com/erikflowers/weather-icons/master/font/weathericons-regular-webfont.ttf"
if [ ! -f "$FONT_PATH" ]; then
    echo "Téléchargement de la police Weather Icons…"
    wget -q -O "$FONT_PATH" "$FONT_URL" && echo "Police téléchargée." || echo "WARN: téléchargement échoué — icônes Unicode de secours utilisées."
else
    echo "Police Weather Icons déjà présente."
fi

echo "Installation terminée."
echo "  mode-airqink  → console + AirQink automatique"
echo "  mode-desktop  → bureau graphique normal"
