#!/bin/bash
# Script d'installation pour Raspberry Pi avec écran e-ink

echo "🌬️  Installation du Moniteur e-ink pour Raspberry Pi"
echo "====================================================="

# Vérifier si on est sur Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Ce script est conçu pour Raspberry Pi"
    echo "Pour tester sur Mac, utilisez: python raspberry_pi_version.py"
fi

# Vérifier si Python 3 est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Installation..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
fi

echo "✅ Python 3 trouvé"

# Mettre à jour le système
echo "📦 Mise à jour du système..."
sudo apt update

# Installer les dépendances système
echo "🔧 Installation des dépendances système..."
sudo apt install -y python3-pil python3-pil.imagetk python3-dev python3-spidev python3-rpi.gpio

# Créer l'environnement virtuel
echo "📦 Création de l'environnement virtuel..."
python3 -m venv venv

# Activer l'environnement virtuel et installer les dépendances
echo "📥 Installation des dépendances Python..."
source venv/bin/activate
pip install -r requirements_raspberry.txt

# Installer la bibliothèque pour l'écran e-ink
echo "🖥️  Installation de la bibliothèque e-ink..."
pip install waveshare-epd

# Créer le fichier .env s'il n'existe pas
if [ ! -f .env ]; then
    echo "📝 Création du fichier de configuration..."
    cp env_example.txt .env
    echo "⚠️  N'oubliez pas de configurer votre clé API dans le fichier .env"
fi

# Créer un service systemd pour le démarrage automatique
echo "⚙️  Configuration du démarrage automatique..."
sudo tee /etc/systemd/system/air-quality-monitor.service > /dev/null <<EOF
[Unit]
Description=Air Quality Monitor e-ink Display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/raspberry_pi_version.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd
sudo systemctl daemon-reload

echo ""
echo "🎉 Installation terminée !"
echo ""
echo "Pour lancer l'application :"
echo "  source venv/bin/activate"
echo "  python raspberry_pi_version.py"
echo ""
echo "Pour activer le démarrage automatique :"
echo "  sudo systemctl enable air-quality-monitor"
echo "  sudo systemctl start air-quality-monitor"
echo ""
echo "Pour voir les logs :"
echo "  sudo journalctl -u air-quality-monitor -f"
