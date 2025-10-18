#!/usr/bin/env python3
"""
Test rapide de la version e-ink
"""

from raspberry_pi_version import EInkAirQualityMonitor

def test_eink_display():
    print("🧪 Test de l'affichage e-ink")
    print("=" * 30)
    
    monitor = EInkAirQualityMonitor()
    
    # Générer des données de test
    data_montreal = monitor._mock_data()
    data_grenoble = monitor._mock_data()
    
    print("📊 Données générées:")
    print(f"Montréal - AQI: {data_montreal['aqi']}, PM2.5: {data_montreal['pm25']}")
    print(f"Grenoble - AQI: {data_grenoble['aqi']}, PM2.5: {data_grenoble['pm25']}")
    
    # Créer l'image e-ink
    image = monitor.create_eink_display(data_montreal, data_grenoble)
    
    # Afficher (sauvegarder en mode simulation)
    monitor.display_on_eink(image)
    
    print("✅ Image e-ink générée avec succès!")

if __name__ == "__main__":
    test_eink_display()
