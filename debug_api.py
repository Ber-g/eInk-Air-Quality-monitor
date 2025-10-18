#!/usr/bin/env python3
"""
Debug de la structure des données API
"""

import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

def debug_api_request():
    """Debug de la requête API"""
    
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if not api_key:
        print("❌ Clé API non trouvée")
        return
    
    print("🔍 Debug de la structure API")
    print("=" * 40)
    
    # Configuration pour Montréal
    lat = 45.5017
    lon = -73.5673
    
    # URL et paramètres
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': api_key
    }
    
    print(f"📍 Coordonnées: {lat}, {lon}")
    print(f"🔗 URL: {url}")
    print(f"📋 Paramètres: {params}")
    print()
    
    # Construire l'URL complète
    full_url = f"{url}?lat={lat}&lon={lon}&appid={api_key}"
    print(f"🌐 URL complète: {full_url}")
    print()
    
    try:
        print("📡 Envoi de la requête...")
        response = requests.get(url, params=params, timeout=10)
        
        print(f"📊 Code de réponse: {response.status_code}")
        print(f"📄 Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Réponse JSON reçue:")
            print(json.dumps(data, indent=2))
            
            # Analyser la structure
            if 'list' in data and len(data['list']) > 0:
                item = data['list'][0]
                print("\n🔍 Structure analysée:")
                print(f"  AQI: {item['main']['aqi']}")
                print(f"  Composants: {item['components']}")
            else:
                print("❌ Structure de réponse inattendue")
        else:
            print(f"❌ Erreur: {response.status_code}")
            print(f"📄 Réponse: {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")

if __name__ == "__main__":
    debug_api_request()
