import json
import pyarrow.parquet as pq
import pandas as pd


from datetime import datetime, timedelta
import random
import math


def read():

    # Odczytaj plik .parquet
    table = pq.read_table("C:\eryk\AppFuga\microgrid_data_5min.parquet")

    # Konwertuj do pandas DataFrame
    df = table.to_pandas()

    # Wyświetl pierwsze kilka wierszy
    print(df)

    print("#################")

    # Pokaż schemat
    print(table.schema)


read()


def convert():

    # Wczytaj plik parquet
    df = pd.read_parquet("C:\eryk\AppFuga\microgrid_data_hourly.parquet")

    # Przekształć DataFrame na format JSON z odpowiednią strukturą
    result = []
    for _, row in df.iterrows():
        record = {
            "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "weather": {
                "temperature": row["temperature"],
                "wind_speed": row["wind_speed"],
                "cloud_cover": row["cloud_cover"],
                "main": row["main"],
            },
            "energy": {
                "consumption": row["consumption"],
                "generation": row["generation"],
            },
            "prices": {"buy_price": row["buy_price"], "sell_price": row["sell_price"]},
        }
        result.append(record)

    # Zapisz do pliku JSON
    with open("microgrid_data_hourly.json", "w") as f:
        json.dump(result, f, indent=2)


# convert()


def generate_weather_energy_data(start_date, num_hours):
    data = []

    # Podstawowe parametry do generowania realistycznych danych
    base_temp = 20  # Średnia temperatura bazowa
    temp_amplitude = 8  # Amplituda dziennych wahań temperatury

    current_time = start_date
    for hour in range(num_hours):
        # Obliczenie pory dnia (0-23)
        hour_of_day = current_time.hour

        # Generowanie temperatury z uwzględnieniem pory dnia
        day_progress = (
            (hour_of_day - 6) * math.pi / 12
        )  # Maksymalna temperatura o 14:00
        temperature = (
            base_temp + temp_amplitude * math.sin(day_progress) + random.uniform(-3, 3)
        )

        # Generowanie zachmurzenia
        cloud_cover = random.randint(0, 100)

        # Określanie pogody na podstawie zachmurzenia
        if cloud_cover < 30:
            weather_main = "Clear"
        elif cloud_cover < 70:
            weather_main = "Partly Cloudy"
        else:
            weather_main = "Cloudy"

        # Generowanie prędkości wiatru
        wind_speed = random.uniform(0, 10)

        # Generowanie produkcji energii (większa w ciągu dnia i przy małym zachmurzeniu)
        day_factor = math.sin(day_progress) if 6 <= hour_of_day <= 18 else 0
        generation = 800 * day_factor * (1 - cloud_cover / 200) + random.uniform(
            -100, 100
        )
        generation = max(0, generation)  # Nie może być ujemna

        # Generowanie zużycia energii (większe w ciągu dnia)
        base_consumption = 700
        consumption = base_consumption + random.uniform(-200, 200)
        if 8 <= hour_of_day <= 20:  # Większe zużycie w ciągu dnia
            consumption *= 1.3

        # Generowanie cen (wyższe w godzinach szczytu)
        base_buy_price = 0.45
        base_sell_price = 0.25
        if 8 <= hour_of_day <= 11 or 16 <= hour_of_day <= 19:  # Godziny szczytu
            price_multiplier = 1.3
        else:
            price_multiplier = 1.0

        buy_price = base_buy_price * price_multiplier + random.uniform(-0.05, 0.05)
        sell_price = base_sell_price * price_multiplier + random.uniform(-0.03, 0.03)

        # Tworzenie rekordu danych
        record = {
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "weather": {
                "temperature": round(temperature, 2),
                "wind_speed": round(wind_speed, 2),
                "cloud_cover": cloud_cover,
                "main": weather_main,
            },
            "energy": {
                "consumption": round(consumption, 1),
                "generation": round(generation, 1),
            },
            "prices": {
                "buy_price": round(buy_price, 2),
                "sell_price": round(sell_price, 2),
            },
        }

        data.append(record)
        current_time += timedelta(hours=1)

    return data


def generate():

    # Generowanie danych dla całego 2024 roku
    start_date = datetime(2024, 1, 1)
    hours_in_year = 365 * 24
    data = generate_weather_energy_data(start_date, hours_in_year)

    # Zapisywanie do pliku JSON
    with open("weather_energy_data_2024.json", "w") as f:
        json.dump(data, f, indent=2)


# generate()
