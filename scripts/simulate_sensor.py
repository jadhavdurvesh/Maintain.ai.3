"""
MAINTAIN AI — Local ESP32 Sensor Simulator
------------------------------------------

This simulates the ESP32 + DHT22 firmware locally.

It sends fake temperature and humidity readings to:
    POST /api/devices/ingest

The device key is intentionally stored directly in this file because
this is only for local development/testing.

TEST FLOW
---------
1. Send normal temperature/humidity readings for a while.
2. Send enough readings to establish a baseline.
3. Introduce a temperature spike.
4. Continue sending readings so the backend can detect the anomaly.

Run this in a THIRD terminal while the backend and frontend are running.
"""

import json
import random
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURATION
# ============================================================

# FastAPI backend running inside the same Codespace
API_BASE_URL = "http://127.0.0.1:8000"

# Device key for the machine you enabled in MAINTAIN AI.
# This is intentionally hard-coded for local testing.
DEVICE_KEY = "f8e216a286e6a7352c6a753b009fd853"

# How often the simulator sends readings
SEND_INTERVAL_SECONDS = 5


# ============================================================
# SIMULATION SETTINGS
# ============================================================

# Normal operating conditions
NORMAL_TEMPERATURE_MIN = 28.0
NORMAL_TEMPERATURE_MAX = 33.0

NORMAL_HUMIDITY_MIN = 45.0
NORMAL_HUMIDITY_MAX = 60.0

# After this many normal cycles, introduce an abnormal condition
BASELINE_CYCLES = 6

# Number of abnormal cycles to send
SPIKE_CYCLES = 5

# Simulated abnormal temperature range
SPIKE_TEMPERATURE_MIN = 52.0
SPIKE_TEMPERATURE_MAX = 62.0

# Simulated abnormal humidity range
SPIKE_HUMIDITY_MIN = 70.0
SPIKE_HUMIDITY_MAX = 85.0


# ============================================================
# HELPERS
# ============================================================

def timestamp():
    """Return a readable local timestamp."""
    return datetime.now().strftime("%H:%M:%S")


def send_reading(reading_type, value, unit):
    """
    Send one simulated sensor reading to the MAINTAIN AI backend.

    Returns True if the backend accepts it.
    """

    url = f"{API_BASE_URL}/api/devices/ingest"

    payload = {
        "reading_type": reading_type,
        "value": round(value, 2),
        "unit": unit,
    }

    body = json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Device-Key": DEVICE_KEY,
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")

            print(
                f"[{timestamp()}] "
                f"{reading_type:<11} "
                f"{value:>6.2f}{unit:<4} "
                f"-> HTTP {response.status}"
            )

            if response_body:
                try:
                    response_json = json.loads(response_body)
                    print(f"             Backend: {response_json}")
                except json.JSONDecodeError:
                    print(f"             Backend: {response_body}")

            return 200 <= response.status < 300

    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")

        print(
            f"[{timestamp()}] "
            f"{reading_type:<11} "
            f"{value:>6.2f}{unit:<4} "
            f"-> HTTP {exc.code} ERROR"
        )

        if error_body:
            print(f"             Backend: {error_body}")

        return False

    except URLError as exc:
        print(
            f"[{timestamp()}] "
            f"{reading_type:<11} "
            f"{value:>6.2f}{unit:<4} "
            f"-> CONNECTION ERROR: {exc.reason}"
        )

        return False

    except TimeoutError:
        print(
            f"[{timestamp()}] "
            f"{reading_type:<11} "
            f"{value:>6.2f}{unit:<4} "
            f"-> TIMEOUT"
        )

        return False

    except Exception as exc:
        print(
            f"[{timestamp()}] "
            f"{reading_type:<11} "
            f"{value:>6.2f}{unit:<4} "
            f"-> ERROR: {exc}"
        )

        return False


def send_cycle(temperature, humidity):
    """Send one temperature + humidity cycle."""

    print()
    print("-" * 65)
    print(f"[{timestamp()}] Sending simulated sensor cycle")
    print("-" * 65)

    temperature_ok = send_reading(
        "temperature",
        temperature,
        "°C",
    )

    humidity_ok = send_reading(
        "humidity",
        humidity,
        "%",
    )

    return temperature_ok and humidity_ok


def normal_readings():
    """Generate realistic normal readings."""

    temperature = random.uniform(
        NORMAL_TEMPERATURE_MIN,
        NORMAL_TEMPERATURE_MAX,
    )

    humidity = random.uniform(
        NORMAL_HUMIDITY_MIN,
        NORMAL_HUMIDITY_MAX,
    )

    return temperature, humidity


def spike_readings():
    """Generate abnormal readings."""

    temperature = random.uniform(
        SPIKE_TEMPERATURE_MIN,
        SPIKE_TEMPERATURE_MAX,
    )

    humidity = random.uniform(
        SPIKE_HUMIDITY_MIN,
        SPIKE_HUMIDITY_MAX,
    )

    return temperature, humidity


# ============================================================
# MAIN SIMULATION
# ============================================================

def main():
    print()
    print("=" * 65)
    print("        MAINTAIN AI — SENSOR SIMULATOR")
    print("=" * 65)
    print()
    print(f"Backend : {API_BASE_URL}")
    print(f"Device  : {DEVICE_KEY}")
    print(f"Interval: {SEND_INTERVAL_SECONDS} seconds")
    print()

    if DEVICE_KEY == "PASTE_YOUR_DEVICE_KEY_HERE":
        print("ERROR: You have not inserted the device key.")
        print()
        print("Open this file and replace:")
        print()
        print('DEVICE_KEY = "PASTE_YOUR_DEVICE_KEY_HERE"')
        print()
        print("with the key from your MAINTAIN AI machine.")
        return

    print("Starting simulation...")
    print()
    print("Phase 1: Establishing normal sensor baseline")
    print()

    # --------------------------------------------------------
    # PHASE 1 — NORMAL BASELINE
    # --------------------------------------------------------

    for cycle in range(1, BASELINE_CYCLES + 1):
        temperature, humidity = normal_readings()

        print(f"\nNormal cycle {cycle}/{BASELINE_CYCLES}")

        send_cycle(
            temperature,
            humidity,
        )

        time.sleep(SEND_INTERVAL_SECONDS)

    # --------------------------------------------------------
    # PHASE 2 — TEMPERATURE SPIKE
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("          ⚠️  STARTING ABNORMAL SPIKE")
    print("=" * 65)
    print()
    print(
        "The next readings are intentionally much higher than the "
        "baseline."
    )
    print(
        "This is intended to test MAINTAIN AI's sensor anomaly detection."
    )
    print()

    for cycle in range(1, SPIKE_CYCLES + 1):
        temperature, humidity = spike_readings()

        print(f"\nSPIKE cycle {cycle}/{SPIKE_CYCLES}")

        send_cycle(
            temperature,
            humidity,
        )

        time.sleep(SEND_INTERVAL_SECONDS)

    # --------------------------------------------------------
    # PHASE 3 — RETURN TO NORMAL
    # --------------------------------------------------------

    print()
    print("=" * 65)
    print("          Returning to normal readings")
    print("=" * 65)
    print()

    while True:
        temperature, humidity = normal_readings()

        send_cycle(
            temperature,
            humidity,
        )

        time.sleep(SEND_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("Simulator stopped by user.")
        print()