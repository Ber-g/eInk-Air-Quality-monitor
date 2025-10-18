#!/usr/bin/env python3
"""
Script pour tester la connexion à l'API OpenWeatherMap
"""

import requests
import time
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def test_api_connection():
    """Teste la connexion à l'API OpenWeatherMap"""
    api_key = os.getenv('OPENWEATHER_API_KEY')
    
    if not api_key:
        print("❌ Clé API non trouvée dans le fichier .env")
        return False
    
    print(f"🔑 Clé API trouvée: {api_key[:8]}...")
    
    # Test avec Montréal
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        'lat': 45.5017,
        'lon': -73.5673,
        'appid': api_key
    }
    
    try:
        print("🌐 Test de connexion à l'API...")
        response = requests.get(url, params=params, timeout=10)
        
        print(f"📊 Code de réponse: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            aqi = data['list'][0]['main']['aqi']
            print(f"✅ API fonctionne ! AQI Montréal: {aqi}")
            return True
        elif response.status_code == 401:
            print("❌ Erreur 401: Clé API invalide ou API non activée")
            print("💡 Vérifiez que l'API 'Air Pollution' est activée sur OpenWeatherMap")
            return False
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

def main():
    print("🧪 Test de l'API OpenWeatherMap")
    print("=" * 40)
    
    if test_api_connection():
        print("\n🎉 Votre API fonctionne parfaitement !")
        print("Vous pouvez maintenant lancer: python air_quality_monitor.py")
    else:
        print("\n⚠️  L'API n'est pas encore prête.")
        print("Vérifiez l'activation sur OpenWeatherMap et réessayez dans quelques minutes.")
        print("\nPour réessayer: python test_api.py")

if __name__ == "__main__":
    main()
