#!/usr/bin/env python3
from __future__ import annotations
"""
Local sensor interface — placeholder for future hardware sensor.
Expected hardware: temperature + humidity (e.g. DHT22, SHT31, SHT40).

To activate: implement _read_hardware() with the appropriate library,
then the rest of the app picks it up automatically via read_sensor().
"""


def read_sensor() -> dict | None:
    """
    Returns:
        {"temperature": float, "humidity": float}  # °C and %RH
    or None if no sensor is connected or the read fails.
    """
    return _read_hardware()


def _read_hardware() -> dict | None:
    # Example — DHT22 on GPIO4 (uncomment + install adafruit-circuitpython-dht):
    #   import adafruit_dht, board
    #   dht = adafruit_dht.DHT22(board.D4)
    #   return {"temperature": dht.temperature, "humidity": dht.humidity}
    #
    # Example — SHT31 via I2C (uncomment + install adafruit-circuitpython-sht31d):
    #   import adafruit_sht31d, board, busio
    #   i2c = busio.I2C(board.SCL, board.SDA)
    #   sht = adafruit_sht31d.SHT31D(i2c)
    #   return {"temperature": sht.temperature, "humidity": sht.relative_humidity}
    return None
