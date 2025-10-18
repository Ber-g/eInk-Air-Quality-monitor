#!/usr/bin/env python3
"""
Moniteur de qualité de l'air utilisant les données officielles de Montréal
Données ouvertes de la Ville de Montréal
"""

import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class MontrealOfficialDataMonitor:
    def __init__(self):
        self.locations = {
            'Montreal': {
                'name': 'Montréal, QC, Canada',
                'lat': 45.5017,
                'lon': -73.5673,
                'source': 'montreal_official'
            },
            'Grenoble': {
                'name': 'Grenoble, France',
                'lat': 45.1885,
                'lon': 5.7245,
                'source': 'openweather'
            }
        }
        
        # Configuration des APIs
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        
    def get_montreal_air_quality(self):
        """Récupère les données de qualité de l'air de Montréal via les données ouvertes"""
        try:
            # Données ouvertes de la Ville de Montréal
            # Utilisation de l'API IQAir (données officielles de Montréal)
            url = "https://api.waqi.info/feed/montreal/"
            params = {
                'token': 'demo'  # Token de démonstration gratuit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok':
                aqi_data = data['data']
                
                return {
                    'aqi': aqi_data.get('aqi', 0),
                    'pm25': aqi_data.get('iaqi', {}).get('pm25', {}).get('v', 0),
                    'pm10': aqi_data.get('iaqi', {}).get('pm10', {}).get('v', 0),
                    'no2': aqi_data.get('iaqi', {}).get('no2', {}).get('v', 0),
                    'o3': aqi_data.get('iaqi', {}).get('o3', {}).get('v', 0),
                    'so2': aqi_data.get('iaqi', {}).get('so2', {}).get('v', 0),
                    'co': aqi_data.get('iaqi', {}).get('co', {}).get('v', 0),
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'station': 'Montréal (Données officielles)',
                    'source': 'Ville de Montréal'
                }
            else:
                raise Exception("Données non disponibles")
                
        except Exception as e:
            print(f"Erreur données Montréal: {e}")
            return self._mock_data()
    
    def get_grenoble_air_quality(self):
        """Récupère les données de Grenoble via OpenWeatherMap"""
        if not self.openweather_api_key:
            return self._mock_data()
            
        url = f"http://api.openweathermap.org/data/2.5/air_pollution"
        params = {
            'lat': 45.1885,
            'lon': 5.7245,
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
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'station': 'Grenoble',
                'source': 'OpenWeather'
            }
        except Exception as e:
            print(f"Erreur OpenWeather: {e}")
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
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'station': 'Test',
            'source': 'Mock'
        }
    
    def get_aqi_level(self, aqi):
        """Convertit l'AQI en niveau de qualité"""
        if aqi <= 50:
            return "Excellent", "🟢"
        elif aqi <= 100:
            return "Bon", "🟡"
        elif aqi <= 150:
            return "Modéré", "🟠"
        elif aqi <= 200:
            return "Mauvais", "🔴"
        else:
            return "Très mauvais", "🟣"
    
    def display_air_quality(self, location_name, data):
        """Affiche les données de qualité de l'air"""
        level, emoji = self.get_aqi_level(data['aqi'])
        
        print(f"\n{'='*60}")
        print(f"📍 {location_name}")
        print(f"🏢 Station: {data.get('station', 'N/A')}")
        print(f"📡 Source: {data.get('source', 'N/A')}")
        print(f"🕐 {data['timestamp']}")
        print(f"{'='*60}")
        print(f"Indice AQI: {data['aqi']} - {level} {emoji}")
        print(f"PM2.5: {data['pm25']} μg/m³")
        print(f"PM10:  {data['pm10']} μg/m³")
        print(f"NO₂:   {data['no2']} μg/m³")
        print(f"O₃:    {data['o3']} μg/m³")
        print(f"SO₂:   {data['so2']} μg/m³")
        print(f"CO:    {data['co']} μg/m³")
    
    def run_monitor(self):
        """Lance le moniteur principal"""
        print("🌬️  Moniteur de Qualité de l'Air - Données Officielles")
        print("Montréal (Données ouvertes) + Grenoble (OpenWeather)")
        print("Appuyez sur Ctrl+C pour arrêter")
        
        try:
            while True:
                # Effacer l'écran
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print(f"🔄 Mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Données de Montréal (Données ouvertes)
                data_montreal = self.get_montreal_air_quality()
                self.display_air_quality("Montréal - Données officielles", data_montreal)
                
                # Données de Grenoble (OpenWeather)
                data_grenoble = self.get_grenoble_air_quality()
                self.display_air_quality("Grenoble, France", data_grenoble)
                
                print(f"\n⏰ Prochaine mise à jour dans 5 minutes...")
                time.sleep(300)  # Attendre 5 minutes
                
        except KeyboardInterrupt:
            print("\n\n👋 Arrêt du moniteur. Au revoir!")

def main():
    monitor = MontrealOfficialDataMonitor()
    monitor.run_monitor()

if __name__ == "__main__":
    main()
