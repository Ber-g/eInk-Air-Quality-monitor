#!/usr/bin/env python3
"""
Test rapide avec les vraies données de l'API
"""

from air_quality_monitor import AirQualityMonitor

def test_real_data():
    print("🌬️  Test avec VRAIES données de l'API")
    print("=" * 50)
    
    monitor = AirQualityMonitor()
    
    print("📊 Récupération des données en temps réel...")
    
    for location_key, location_data in monitor.locations.items():
        print(f"\n🔄 Récupération des données pour {location_data['name']}...")
        data = monitor.get_air_quality_openweather(
            location_data['lat'], 
            location_data['lon']
        )
        monitor.display_air_quality(location_data['name'], data)
    
    print("\n" + "="*50)
    print("✅ Test avec vraies données terminé!")

if __name__ == "__main__":
    test_real_data()
