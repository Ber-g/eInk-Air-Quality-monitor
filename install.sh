#!/bin/bash
# Script d'installation pour le moniteur de qualité de l'air

echo "🌬️  Installation du Moniteur de Qualité de l'Air"
echo "================================================"

# Vérifier si Python 3 est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Veuillez l'installer d'abord."
    exit 1
fi

echo "✅ Python 3 trouvé"

# Créer l'environnement virtuel
echo "📦 Création de l'environnement virtuel..."
python3 -m venv venv

# Activer l'environnement virtuel et installer les dépendances
echo "📥 Installation des dépendances..."
source venv/bin/activate
pip install -r requirements.txt

# Créer le fichier .env s'il n'existe pas
if [ ! -f .env ]; then
    echo "📝 Création du fichier de configuration..."
    cp env_example.txt .env
    echo "⚠️  N'oubliez pas de configurer votre clé API dans le fichier .env"
fi

echo ""
echo "🎉 Installation terminée !"
echo ""
echo "Pour lancer l'application :"
echo "  source venv/bin/activate"
echo "  python air_quality_monitor.py"
echo ""
echo "Pour tester :"
echo "  source venv/bin/activate"
echo "  python test_mac.py"
