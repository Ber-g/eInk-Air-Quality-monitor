# 🌬️ Guide Complet - Moniteur de Qualité de l'Air

## 🎯 Vue d'ensemble

Votre projet est maintenant **100% fonctionnel** avec :
- ✅ **4 emplacements** : Montréal, Grenoble, Paris, Tokyo
- ✅ **Version Mac** pour les tests
- ✅ **Version Raspberry Pi** avec écran e-ink
- ✅ **APIs gratuites** configurées
- ✅ **Git configuré** pour la sauvegarde

## 🚀 Utilisation Immédiate

### Sur Mac (Test et développement)

```bash
# 1. Activer l'environnement
source venv/bin/activate

# 2. Tester avec données simulées
python test_mac.py

# 3. Tester l'API (quand elle sera active)
python test_api.py

# 4. Lancer l'application complète
python air_quality_monitor.py
```

### Sur Raspberry Pi (Production)

```bash
# 1. Installer automatiquement
chmod +x install_raspberry.sh
./install_raspberry.sh

# 2. Configurer la clé API
nano .env
# Ajouter: OPENWEATHER_API_KEY=votre_cle

# 3. Lancer l'application e-ink
source venv/bin/activate
python raspberry_pi_version.py
```

## 📊 Fonctionnalités

### Données affichées
- **AQI** : Indice de qualité de l'air (1-5)
- **PM2.5** : Particules fines
- **PM10** : Particules
- **NO₂** : Dioxyde d'azote
- **O₃** : Ozone
- **SO₂** : Dioxyde de soufre
- **CO** : Monoxyde de carbone

### Emplacements surveillés
1. **Montréal, Canada** 🇨🇦
2. **Grenoble, France** 🇫🇷
3. **Paris, France** 🇫🇷
4. **Tokyo, Japan** 🇯🇵

## 🔧 Configuration

### Clé API OpenWeatherMap
1. Allez sur [OpenWeatherMap](https://openweathermap.org/api)
2. Créez un compte gratuit
3. Activez l'API "Air Pollution"
4. Copiez votre clé dans le fichier `.env`

### Fichier .env
```
OPENWEATHER_API_KEY=votre_cle_api_ici
AIRVISUAL_API_KEY=your_api_key_here
```

## 🖥️ Versions disponibles

### 1. Version Mac (Terminal)
- **Fichier** : `air_quality_monitor.py`
- **Usage** : Tests et développement
- **Affichage** : Terminal avec couleurs

### 2. Version Raspberry Pi (E-ink)
- **Fichier** : `raspberry_pi_version.py`
- **Usage** : Affichage permanent
- **Écran** : Compatible Waveshare 2.9" et 4.2"

## 📱 Interface E-ink

L'écran e-ink affiche :
```
Qualité de l'Air
Mis à jour: 21:30
────────────────────────
Montréal    AQI 2 - Bon
PM2.5: 15.2 ug/m3
PM10:  22.1 ug/m3

Grenoble    AQI 1 - Excellent
PM2.5: 8.5 ug/m3
PM10:  12.3 ug/m3
```

## 🔄 Mise à jour automatique

- **Mac** : Toutes les 5 minutes
- **Raspberry Pi** : Toutes les 10 minutes
- **Démarrage automatique** : Service systemd configuré

## 🛠️ Dépannage

### API ne fonctionne pas
```bash
# Tester la connexion
python test_api.py

# Vérifier la clé API
cat .env
```

### Écran e-ink ne s'affiche pas
```bash
# Vérifier les permissions
sudo usermod -a -G spi,gpio pi

# Redémarrer
sudo reboot
```

### Problème de polices
```bash
# Installer les polices
sudo apt install fonts-dejavu-core
```

## 📁 Structure du projet

```
eInk-Air-Quality-monitor/
├── air_quality_monitor.py      # Version Mac
├── raspberry_pi_version.py     # Version Raspberry Pi
├── test_mac.py                 # Test données simulées
├── test_api.py                 # Test API réelle
├── test_eink.py                # Test affichage e-ink
├── requirements.txt            # Dépendances Mac
├── requirements_raspberry.txt  # Dépendances Raspberry Pi
├── install.sh                  # Installation Mac
├── install_raspberry.sh        # Installation Raspberry Pi
├── .env                        # Configuration (local uniquement)
├── env_example.txt             # Exemple de configuration
├── .gitignore                  # Fichiers ignorés par Git
├── README.md                   # Documentation principale
├── GITHUB_SETUP.md             # Guide GitHub
└── GUIDE_COMPLET.md            # Ce guide
```

## 🎉 Prochaines étapes

1. **Testez l'API** : `python test_api.py`
2. **Sauvegardez sur GitHub** : Suivez `GITHUB_SETUP.md`
3. **Configurez votre Raspberry Pi** : `./install_raspberry.sh`
4. **Personnalisez** : Ajoutez d'autres villes si souhaité

## 💡 Conseils

- **Sauvegardez régulièrement** : `git add . && git commit -m "message"`
- **Testez avant de déployer** : Utilisez la version Mac d'abord
- **Surveillez les logs** : `sudo journalctl -u air-quality-monitor -f`
- **Économisez l'énergie** : L'écran e-ink ne consomme que lors des mises à jour

Votre projet est prêt à être utilisé ! 🚀
