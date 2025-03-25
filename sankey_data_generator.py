import json
from datetime import datetime, timedelta
import random
import math


def generate_device_base():
    """Generuje podstawową strukturę urządzenia"""
    return {"switch_status": True, "device_status": "online"}


def generate_power_sources():
    """Generuje strukturę źródeł energii"""
    sources = {"pv_panels": [], "wind_turbines": [], "fuel_turbines": []}

    # Generowanie paneli PV
    for i in range(3):
        sources["pv_panels"].append(
            {
                **generate_device_base(),
                "id": i + 1,
                "name": f"PV Panel {i + 1}",
                "priority": 1,
                "actual_output": 0,  # będzie aktualizowane w generatorze
            }
        )

    # Generowanie turbin wiatrowych
    for i in range(3):
        sources["wind_turbines"].append(
            {
                **generate_device_base(),
                "id": i + 10,
                "name": f"Wind Turbine {i + 1}",
                "priority": 2,
                "actual_output": 0,
            }
        )

    # Generowanie turbin paliwowych
    for i in range(3):
        sources["fuel_turbines"].append(
            {
                **generate_device_base(),
                "id": i + 20,
                "name": f"Fuel Turbine {i + 1}",
                "priority": 3,
                "actual_output": 0,
            }
        )

    return sources


def generate_consumption_devices():
    """Generuje strukturę urządzeń zużywających energię"""
    return {
        "adjustable_devices": [
            {"id": 101, "name": "HVAC System", "consumption": 0, "priority": 1},
            {"id": 102, "name": "Water Heater", "consumption": 0, "priority": 2},
            {"id": 103, "name": "EV Charger", "consumption": 0, "priority": 3},
        ],
        "non_adjustable_devices": [
            {"id": 201, "name": "Lighting", "consumption": 0},
            {"id": 202, "name": "Data Center", "consumption": 0},
            {"id": 203, "name": "Security Systems", "consumption": 0},
        ],
    }


def calculate_pv_output(hour):
    """Oblicza generację energii z paneli PV"""
    if 6 <= hour <= 18:  # dzień
        base = math.sin((hour - 6) * math.pi / 12) * 100  # maksymalna generacja 100 kW
        return base * random.uniform(0.7, 1.0)
    return 0


def calculate_wind_output():
    """Oblicza generację energii z turbin wiatrowych"""
    return random.uniform(20, 80)  # generacja między 20 a 80 kW


def generate_energy_flow_data(start_date, num_hours):
    """Generuje dane przepływu energii"""
    data = []

    current_time = start_date
    for hour in range(num_hours):
        # Inicjalizacja źródeł i zużycia
        power_sources = generate_power_sources()
        consumption_devices = generate_consumption_devices()

        hour_of_day = current_time.hour

        # Obliczanie generacji
        total_pv = 0
        for panel in power_sources["pv_panels"]:
            panel["actual_output"] = round(calculate_pv_output(hour_of_day), 2)
            total_pv += panel["actual_output"]

        total_wind = 0
        for turbine in power_sources["wind_turbines"]:
            turbine["actual_output"] = round(calculate_wind_output(), 2)
            total_wind += turbine["actual_output"]

        total_fuel = 0
        for turbine in power_sources["fuel_turbines"]:
            turbine["actual_output"] = round(
                random.uniform(30, 90), 2
            )  # stała generacja między 30 a 90 kW
            total_fuel += turbine["actual_output"]

        # Obliczanie zużycia
        total_adjustable = 0
        for device in consumption_devices["adjustable_devices"]:
            if 8 <= hour_of_day <= 20:  # większe zużycie w ciągu dnia
                device["consumption"] = round(random.uniform(20, 100), 2)
            else:
                device["consumption"] = round(random.uniform(5, 30), 2)
            total_adjustable += device["consumption"]

        total_non_adjustable = 0
        for device in consumption_devices["non_adjustable_devices"]:
            device["consumption"] = round(random.uniform(10, 50), 2)
            total_non_adjustable += device["consumption"]

        # Obliczanie całkowitych sum
        total_local_generation = total_pv + total_wind + total_fuel
        total_consumption = total_adjustable + total_non_adjustable

        # Obliczanie poboru z sieci (jeśli potrzebny)
        grid_power = max(0, total_consumption - total_local_generation)

        # Tworzenie rekordu z sumami
        record = {
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "power_sources": {
                **power_sources,
                "grid_power": round(grid_power, 2),
                "generation_summary": {
                    "total_pv_generation": round(total_pv, 2),
                    "total_wind_generation": round(total_wind, 2),
                    "total_fuel_generation": round(total_fuel, 2),
                    "total_local_generation": round(total_local_generation, 2),
                },
            },
            "consumption": {
                **consumption_devices,
                "consumption_summary": {
                    "total_adjustable_consumption": round(total_adjustable, 2),
                    "total_non_adjustable_consumption": round(total_non_adjustable, 2),
                    "total_consumption": round(total_consumption, 2),
                },
            },
        }

        data.append(record)
        current_time += timedelta(hours=1)

    return data


# Generowanie danych dla przykładowego okresu
start_date = datetime(2024, 1, 1)
hours_to_generate = 24 * 7  # tydzień danych
data = generate_energy_flow_data(start_date, hours_to_generate)

# Zapisywanie do pliku JSON
with open("energy_flow_data.json", "w") as f:
    json.dump(data, f, indent=2)
