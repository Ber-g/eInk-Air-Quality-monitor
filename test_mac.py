#!/usr/bin/env python3
"""
Script de test simple pour vérifier que tout fonctionne sur Mac
"""

from air_quality_monitor import AirQualityMonitor

def test_basic():
    print("🧪 Test du moniteur de qualité de l'air")
    print("=" * 40)
    
    monitor = AirQualityMonitor()
    
    # Test avec des données mockées
    print("Test avec données simulées...")
    for location_key, location_data in monitor.locations.items():
        data = monitor._mock_data()
        monitor.display_air_quality(location_data['name'], data)
    
    print("\n✅ Test terminé avec succès!")
    print("Pour tester avec de vraies données, configurez votre clé API dans le fichier .env")

if __name__ == "__main__":
    test_basic()
