#!/usr/bin/env python3
"""
Test des données officielles de Montréal
"""

from montreal_official_data import MontrealOfficialDataMonitor

def test_official_data():
    print("🧪 Test des données officielles de Montréal")
    print("=" * 50)
    
    monitor = MontrealOfficialDataMonitor()
    
    # Test des données de Montréal
    print("📊 Test des données officielles de Montréal...")
    data_montreal = monitor.get_montreal_air_quality()
    monitor.display_air_quality("Montréal - Données officielles", data_montreal)
    
    print("\n" + "="*50)
    print("✅ Test terminé!")

if __name__ == "__main__":
    test_official_data()
