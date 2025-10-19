#!/usr/bin/env python3
"""
Moniteur de qualité de l'air pour Raspberry Pi avec écran e-ink
Version de test pour Mac - affichage dans le terminal
"""

import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class AirQualityMonitor:
    def __init__(self):
        self.locations = {
          'Montreal': {
                'name': 'Montréal',
                'lat': 45.49045,
                'lon': -73.6446,
                'api': 'openweather'
            },
            'Grenoble': {
                'name': 'Grenoble, France',
                'lat': 45.1885,
                'lon': 5.7245,
                'api': 'openweather'
            },
            'Paris': {
                'name': 'Paris, France',
                'lat': 48.8566,
                'lon': 2.3522,
                'api': 'openweather'
            },
            'Tokyo': {
                'name': 'Tokyo, Japan',
                'lat': 35.6762,
                'lon': 139.6503,
                'api': 'openweather'
            }
        }
        
        # Configuration des APIs
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        self.airvisual_api_key = os.getenv('AIRVISUAL_API_KEY')
        
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
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
        except Exception as e:
            print(f"Erreur OpenWeather: {e}")
            return self._mock_data()
    
    def _mock_data(self):
        """Données de test quand les APIs ne sont pas disponibles"""
        import random
        return {
            'aqi': random.randint(1, 5),
            'pm25': round(random.uniform(10, 50), 1),
            'pm10': round(random.uniform(15, 60), 1),
            'no2': round(random.uniform(20, 80), 1),
            'o3': round(random.uniform(30, 120), 1),
            'so2': round(random.uniform(5, 25), 1),
            'co': round(random.uniform(200, 800), 1),
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
    
    def get_aqi_level(self, aqi):
        """Convertit l'AQI en niveau de qualité"""
        if aqi <= 1:
            return "Excellent", "🟢"
        elif aqi <= 2:
            return "Bon", "🟡"
        elif aqi <= 3:
            return "Modéré", "🟠"
        elif aqi <= 4:
            return "Mauvais", "🔴"
        else:
            return "Très mauvais", "🟣"
    
    def get_pollutant_level(self, pollutant, value):
        """Évalue le niveau d'un polluant spécifique"""
        # Seuils basés sur les recommandations de l'OMS et de l'UE
        
        if pollutant == 'pm25':
            if value <= 10:
                return "Excellent", "🟢"
            elif value <= 25:
                return "Bon", "🟡"
            elif value <= 35:
                return "Modéré", "🟠"
            elif value <= 50:
                return "Mauvais", "🔴"
            else:
                return "Dangereux", "🟣"
                
        elif pollutant == 'pm10':
            if value <= 20:
                return "Excellent", "🟢"
            elif value <= 40:
                return "Bon", "🟡"
            elif value <= 50:
                return "Modéré", "🟠"
            elif value <= 100:
                return "Mauvais", "🔴"
            else:
                return "Dangereux", "🟣"
                
        elif pollutant == 'no2':
            if value <= 25:
                return "Excellent", "🟢"
            elif value <= 40:
                return "Bon", "🟡"
            elif value <= 50:
                return "Modéré", "🟠"
            elif value <= 100:
                return "Mauvais", "🔴"
            else:
                return "Dangereux", "🟣"
                
        elif pollutant == 'o3':
            if value <= 60:
                return "Excellent", "🟢"
            elif value <= 100:
                return "Bon", "🟡"
            elif value <= 120:
                return "Modéré", "🟠"
            elif value <= 180:
                return "Mauvais", "🔴"
            else:
                return "Dangereux", "🟣"
                
        elif pollutant == 'so2':
            if value <= 20:
                return "Excellent", "🟢"
            elif value <= 40:
                return "Bon", "🟡"
            elif value <= 50:
                return "Modéré", "🟠"
            elif value <= 100:
                return "Mauvais", "🔴"
            else:
                return "Dangereux", "🟣"
                
        elif pollutant == 'co':
            if value <= 200:
                return "Excellent", "🟢"
            elif value <= 400:
                return "Bon", "🟡"
            elif value <= 500:
                return "Modéré", "🟠"
            elif value <= 1000:
                return "Mauvais", "🔴"
            else:
                return "Dangereux", "🟣"
        
        return "Inconnu", "⚪"
    
    def display_air_quality(self, location_name, data):
        """Affiche les données de qualité de l'air"""
        level, emoji = self.get_aqi_level(data['aqi'])
        
        print(f"\n{'='*60}")
        print(f"📍 {location_name}")
        print(f"🕐 {data['timestamp']}")
        print(f"{'='*60}")
        print(f"Indice AQI: {data['aqi']} - {level} {emoji}")
        print(f"{'='*60}")
        
        # Affichage des polluants avec leurs niveaux
        pm25_level, pm25_emoji = self.get_pollutant_level('pm25', data['pm25'])
        pm10_level, pm10_emoji = self.get_pollutant_level('pm10', data['pm10'])
        no2_level, no2_emoji = self.get_pollutant_level('no2', data['no2'])
        o3_level, o3_emoji = self.get_pollutant_level('o3', data['o3'])
        so2_level, so2_emoji = self.get_pollutant_level('so2', data['so2'])
        co_level, co_emoji = self.get_pollutant_level('co', data['co'])
        
        print(f"PM2.5: {data['pm25']:5.1f} μg/m³ - {pm25_level} {pm25_emoji}")
        print(f"PM10:  {data['pm10']:5.1f} μg/m³ - {pm10_level} {pm10_emoji}")
        print(f"NO₂:   {data['no2']:5.1f} μg/m³ - {no2_level} {no2_emoji}")
        print(f"O₃:    {data['o3']:5.1f} μg/m³ - {o3_level} {o3_emoji}")
        print(f"SO₂:   {data['so2']:5.1f} μg/m³ - {so2_level} {so2_emoji}")
        print(f"CO:    {data['co']:5.1f} μg/m³ - {co_level} {co_emoji}")
    
    def run_monitor(self):
        """Lance le moniteur principal"""
        print("🌬️  Moniteur de Qualité de l'Air")
        print("Appuyez sur Ctrl+C pour arrêter")
        
        try:
            while True:
                # Effacer l'écran (fonctionne sur Mac/Linux)
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print(f"🔄 Mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                for location_key, location_data in self.locations.items():
                    data = self.get_air_quality_openweather(
                        location_data['lat'], 
                        location_data['lon']
                    )
                    self.display_air_quality(location_data['name'], data)
                
                print(f"\n⏰ Prochaine mise à jour dans 5 minutes...")
                time.sleep(300)  # Attendre 5 minutes
                
        except KeyboardInterrupt:
            print("\n\n👋 Arrêt du moniteur. Au revoir!")

def main():
    monitor = AirQualityMonitor()
    monitor.run_monitor()

if __name__ == "__main__":
    main()
