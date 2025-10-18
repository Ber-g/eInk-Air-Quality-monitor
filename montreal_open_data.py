#!/usr/bin/env python3
"""
Moniteur de qualité de l'air utilisant les données ouvertes de Montréal
Inclut les données du carrefour Décarie
"""

import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class MontrealOpenDataMonitor:
    def __init__(self):
        self.locations = {
            'Decarie': {
                'name': 'Carrefour Décarie, Montréal',
                'station_id': 'Décarie',  # ID de la station RSQA
                'lat': 45.5017,
                'lon': -73.5673
            },
            'Grenoble': {
                'name': 'Grenoble, France',
                'lat': 45.1885,
                'lon': 5.7245,
                'api': 'openweather'  # Garder OpenWeather pour Grenoble
            }
        }
        
        # Configuration des APIs
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        
    def get_montreal_air_quality(self):
        """Récupère les données de qualité de l'air de Montréal via RSQA"""
        try:
            # API RSQA - données en temps réel
            url = "https://rsqa.ca/api/v1/current"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Chercher la station Décarie
            decarie_data = None
            for station in data.get('stations', []):
                if 'Décarie' in station.get('name', ''):
                    decarie_data = station
                    break
            
            if not decarie_data:
                # Si pas de données Décarie, prendre la première station disponible
                decarie_data = data.get('stations', [{}])[0]
            
            # Extraire les données
            measurements = decarie_data.get('measurements', {})
            
            return {
                'aqi': self._calculate_aqi_montreal(measurements),
                'pm25': measurements.get('PM2.5', 0),
                'pm10': measurements.get('PM10', 0),
                'no2': measurements.get('NO2', 0),
                'o3': measurements.get('O3', 0),
                'so2': measurements.get('SO2', 0),
                'co': measurements.get('CO', 0),
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'station': decarie_data.get('name', 'Montréal'),
                'source': 'RSQA'
            }
            
        except Exception as e:
            print(f"Erreur RSQA: {e}")
            return self._mock_data()
    
    def _calculate_aqi_montreal(self, measurements):
        """Calcule un AQI basé sur les données de Montréal"""
        # Calcul simplifié basé sur PM2.5 (standard canadien)
        pm25 = measurements.get('PM2.5', 0)
        
        if pm25 <= 10:
            return 1  # Excellent
        elif pm25 <= 20:
            return 2  # Bon
        elif pm25 <= 30:
            return 3  # Modéré
        elif pm25 <= 40:
            return 4  # Mauvais
        else:
            return 5  # Très mauvais
    
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
        print("🌬️  Moniteur de Qualité de l'Air - Données Ouvertes")
        print("Montréal (RSQA) + Grenoble (OpenWeather)")
        print("Appuyez sur Ctrl+C pour arrêter")
        
        try:
            while True:
                # Effacer l'écran
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print(f"🔄 Mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Données de Montréal (RSQA)
                data_montreal = self.get_montreal_air_quality()
                self.display_air_quality("Montréal - Carrefour Décarie", data_montreal)
                
                # Données de Grenoble (OpenWeather)
                data_grenoble = self.get_grenoble_air_quality()
                self.display_air_quality("Grenoble, France", data_grenoble)
                
                print(f"\n⏰ Prochaine mise à jour dans 5 minutes...")
                time.sleep(300)  # Attendre 5 minutes
                
        except KeyboardInterrupt:
            print("\n\n👋 Arrêt du moniteur. Au revoir!")

def main():
    monitor = MontrealOpenDataMonitor()
    monitor.run_monitor()

if __name__ == "__main__":
    main()
