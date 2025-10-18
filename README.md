# eInk Air Quality Monitor

Un moniteur de qualité de l'air pour Raspberry Pi avec écran e-ink, affichant les données de 4 emplacements dans le monde.

## 🎯 Fonctionnalités

- Affichage de la qualité de l'air pour Montréal et Grenoble (et 2 autres emplacements à venir)
- Interface optimisée pour écran e-ink
- Mise à jour automatique des données
- Version de test pour Mac/Linux

## 🚀 Installation

### Prérequis
- Python 3.7+
- Clé API OpenWeatherMap (gratuite)

### Installation des dépendances

```bash
pip install -r requirements.txt
```

### Configuration

1. Copiez le fichier d'exemple de configuration :
```bash
cp env_example.txt .env
```

2. Éditez le fichier `.env` et ajoutez votre clé API OpenWeatherMap :
```
OPENWEATHER_API_KEY=votre_cle_api_ici
```

### Obtenir une clé API gratuite

1. Allez sur [OpenWeatherMap](https://openweathermap.org/api)
2. Créez un compte gratuit
3. Activez l'API "Air Pollution"
4. Copiez votre clé API dans le fichier `.env`

## 🖥️ Utilisation

### Version de test (Mac/Linux)

```bash
python air_quality_monitor.py
```

Cette version affiche les données dans le terminal et se met à jour toutes les 5 minutes.

### Version Raspberry Pi (à venir)

La version pour Raspberry Pi avec écran e-ink sera disponible prochainement.

## 📊 Données affichées

- **AQI** : Indice de qualité de l'air (1-5)
- **PM2.5** : Particules fines (μg/m³)
- **PM10** : Particules (μg/m³)
- **NO₂** : Dioxyde d'azote (μg/m³)
- **O₃** : Ozone (μg/m³)
- **SO₂** : Dioxyde de soufre (μg/m³)
- **CO** : Monoxyde de carbone (μg/m³)

## 🏗️ Structure du projet

```
eInk-Air-Quality-monitor/
├── air_quality_monitor.py    # Application principale
├── requirements.txt          # Dépendances Python
├── env_example.txt          # Exemple de configuration
├── README.md                # Ce fichier
└── LICENSE                  # Licence CC0
```

## 🔧 Développement

### Prochaines étapes

1. ✅ Version de test pour Mac
2. 🔄 Intégration des APIs de qualité de l'air
3. ⏳ Interface e-ink pour Raspberry Pi
4. ⏳ Ajout de 2 emplacements supplémentaires
5. ⏳ Configuration Git/GitHub

## 📝 Licence

Ce projet est sous licence CC0 - domaine public.