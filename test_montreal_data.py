#!/usr/bin/env python3
"""
Test des données ouvertes de Montréal
"""

from montreal_open_data import MontrealOpenDataMonitor

def test_montreal_data():
    print("🧪 Test des données ouvertes de Montréal")
    print("=" * 50)
    
    monitor = MontrealOpenDataMonitor()
    
    # Test des données de Montréal
    print("📊 Test des données RSQA (Montréal)...")
    data_montreal = monitor.get_montreal_air_quality()
    monitor.display_air_quality("Montréal - Carrefour Décarie", data_montreal)
    
    print("\n" + "="*50)
    print("✅ Test terminé!")

if __name__ == "__main__":
    test_montreal_data()
