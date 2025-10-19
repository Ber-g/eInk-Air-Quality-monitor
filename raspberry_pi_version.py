#!/usr/bin/env python3
"""
Version Raspberry Pi avec écran e-ink pour le moniteur de qualité de l'air
Compatible avec les écrans e-ink Waveshare 2.9" et 4.2"
"""

import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Import pour l'écran e-ink (à installer sur Raspberry Pi)
try:
    from waveshare_epd import epd2in9_V2
    EINK_AVAILABLE = True
except ImportError:
    EINK_AVAILABLE = False
    print("⚠️  Écran e-ink non disponible - mode simulation")

from PIL import Image, ImageDraw, ImageFont

# Charger les variables d'environnement
load_dotenv()

class EInkAirQualityMonitor:
    def __init__(self):
        self.locations = {
            'Montreal': {
                'name': 'Montréal',
                'lat': 45.49045,
                'lon': -73.6446,
                'api': 'openweather'
            },
            'Grenoble': {
                'name': 'Grenoble',
                'lat': 45.1885,
                'lon': 5.7245,
                'api': 'openweather'
            },
            'Paris': {
                'name': 'Paris',
                'lat': 48.8566,
                'lon': 2.3522,
                'api': 'openweather'
            },
            'Tokyo': {
                'name': 'Tokyo',
                'lat': 35.6762,
                'lon': 139.6503,
                'api': 'openweather'
            }
        }
        
        # Configuration des APIs
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        
        # Configuration de l'écran e-ink
        if EINK_AVAILABLE:
            self.epd = epd2in9_V2.EPD()
            self.epd.init()
            self.width = self.epd.width
            self.height = self.epd.height
        else:
            # Mode simulation pour Mac
            self.width = 296
            self.height = 128
        
        # Polices (à adapter selon votre système)
        try:
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            self.font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except:
            # Polices par défaut
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
    def get_air_quality_openweather(self, lat, lon):
        """Récupère la qualité de l'air via OpenWeatherMap API"""
        if not self.openweather_api_key:
            return self._mock_data()
            
        url = f"http://api.openweathermap.org/data/2.5/air_pollution"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.openweather_api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            aqi = data['list'][0]['main']['aqi']
            components = data['list'][0]['components']
            
            return {
                'aqi': aqi,
                'pm25': components.get('pm2_5', 0),
                'pm10': components.get('pm10', 0),
                'no2': components.get('no2', 0),
                'o3': components.get('o3', 0),
                'so2': components.get('so2', 0),
                'co': components.get('co', 0),
                'timestamp': datetime.now().strftime('%H:%M')
            }
        except Exception as e:
            print(f"Erreur API: {e}")
            return self._mock_data()
    
    def _mock_data(self):
        """Données de test"""
        import random
        return {
            'aqi': random.randint(1, 5),
            'pm25': round(random.uniform(10, 50), 1),
            'pm10': round(random.uniform(15, 60), 1),
            'no2': round(random.uniform(20, 80), 1),
            'o3': round(random.uniform(30, 120), 1),
            'so2': round(random.uniform(5, 25), 1),
            'co': round(random.uniform(200, 800), 1),
            'timestamp': datetime.now().strftime('%H:%M')
        }
    
    def get_aqi_info(self, aqi):
        """Convertit l'AQI en niveau et couleur"""
        if aqi <= 1:
            return "Excellent", "🟢", (0, 255, 0)
        elif aqi <= 2:
            return "Bon", "🟡", (255, 255, 0)
        elif aqi <= 3:
            return "Modéré", "🟠", (255, 165, 0)
        elif aqi <= 4:
            return "Mauvais", "🔴", (255, 0, 0)
        else:
            return "Très mauvais", "🟣", (128, 0, 128)
    
    def create_eink_display(self, data_montreal, data_grenoble):
        """Crée l'affichage pour l'écran e-ink"""
        # Créer une image noire et blanche
        image = Image.new('1', (self.width, self.height), 255)  # Blanc
        draw = ImageDraw.Draw(image)
        
        # Titre
        draw.text((10, 5), "Qualité de l'Air", font=self.font_large, fill=0)
        draw.text((10, 25), f"Mis à jour: {data_montreal['timestamp']}", font=self.font_small, fill=0)
        
        # Ligne séparatrice
        draw.line([(10, 40), (self.width-10, 40)], fill=0, width=1)
        
        # Montréal
        level_mtl, emoji_mtl, color_mtl = self.get_aqi_info(data_montreal['aqi'])
        draw.text((10, 50), "Montréal", font=self.font_medium, fill=0)
        draw.text((80, 50), f"AQI {data_montreal['aqi']} - {level_mtl}", font=self.font_medium, fill=0)
        draw.text((10, 65), f"PM2.5: {data_montreal['pm25']} ug/m3", font=self.font_small, fill=0)
        draw.text((10, 78), f"PM10:  {data_montreal['pm10']} ug/m3", font=self.font_small, fill=0)
        
        # Grenoble
        level_gr, emoji_gr, color_gr = self.get_aqi_info(data_grenoble['aqi'])
        draw.text((10, 95), "Grenoble", font=self.font_medium, fill=0)
        draw.text((80, 95), f"AQI {data_grenoble['aqi']} - {level_gr}", font=self.font_medium, fill=0)
        draw.text((10, 110), f"PM2.5: {data_grenoble['pm25']} ug/m3", font=self.font_small, fill=0)
        draw.text((10, 123), f"PM10:  {data_grenoble['pm10']} ug/m3", font=self.font_small, fill=0)
        
        return image
    
    def display_on_eink(self, image):
        """Affiche l'image sur l'écran e-ink"""
        if EINK_AVAILABLE:
            # Vraie écran e-ink
            self.epd.display(self.epd.getbuffer(image))
        else:
            # Mode simulation - sauvegarder l'image
            image.save('eink_simulation.png')
            print("🖼️  Image e-ink simulée sauvegardée: eink_simulation.png")
    
    def run_monitor(self):
        """Lance le moniteur principal"""
        print("🌬️  Moniteur e-ink de Qualité de l'Air")
        print("Appuyez sur Ctrl+C pour arrêter")
        
        try:
            while True:
                print(f"🔄 Mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Récupérer les données
                data_montreal = self.get_air_quality_openweather(
                    self.locations['Montreal']['lat'], 
                    self.locations['Montreal']['lon']
                )
                data_grenoble = self.get_air_quality_openweather(
                    self.locations['Grenoble']['lat'], 
                    self.locations['Grenoble']['lon']
                )
                
                # Créer et afficher l'image
                image = self.create_eink_display(data_montreal, data_grenoble)
                self.display_on_eink(image)
                
                print("✅ Affichage mis à jour")
                print("⏰ Prochaine mise à jour dans 10 minutes...")
                time.sleep(600)  # Attendre 10 minutes
                
        except KeyboardInterrupt:
            print("\n\n👋 Arrêt du moniteur. Au revoir!")
            if EINK_AVAILABLE:
                self.epd.sleep()

def main():
    monitor = EInkAirQualityMonitor()
    monitor.run_monitor()

if __name__ == "__main__":
    main()
