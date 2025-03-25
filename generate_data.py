import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


class DataGenerator:
    def __init__(self, base_directory):
        self.base_directory = base_directory
        self.random = np.random.RandomState()

    def generate_five_minute_data(self, date):
        """Generuje dane 5-minutowe dla podanego dnia."""
        # Utwórz zakres czasowy dla danego dnia (288 próbek = 24h * 12 próbek/h)
        timestamps = pd.date_range(
            start=date.replace(hour=0, minute=0),
            end=(date + timedelta(days=1)).replace(hour=0, minute=0),
            freq="5T",
        )[
            :-1
        ]  # Usuń ostatni element (początek następnego dnia)

        data = []
        for timestamp in timestamps:
            hour = timestamp.hour
            data.append(self._generate_single_record(timestamp, hour))

        # Konwersja do DataFrame
        df = pd.DataFrame(data)

        # Upewnij się, że katalog istnieje
        directory = os.path.join(self.base_directory, "5min")
        os.makedirs(directory, exist_ok=True)

        # Zapisz do pliku parquet
        file_path = os.path.join(directory, f"{date.strftime('%Y-%m-%d')}.parquet")
        df.to_parquet(file_path, index=False)

        print(f"Generated {len(data)} records for {date.strftime('%Y-%m-%d')}")
        return df

    def _generate_single_record(self, timestamp, hour):
        """Generuje pojedynczy rekord danych."""
        base_consumption = self._get_base_consumption(hour)
        base_generation = self._get_base_generation(hour)
        base_temperature = self._get_base_temperature(hour)

        # Dodaj losowe wariacje
        consumption = base_consumption * (
            0.9 + self.random.random() * 0.2
        )  # ±10% wariacji
        generation = base_generation * (0.9 + self.random.random() * 0.2)
        temperature = base_temperature + (self.random.random() * 2 - 1)  # ±1°C wariacji
        wind_speed = self.random.random() * 10
        cloud_cover = self.random.randint(0, 100)
        buy_price = 0.4 + self.random.random() * 0.3
        sell_price = 0.2 + self.random.random() * 0.2

        return {
            "timestamp": timestamp,
            "consumption": round(consumption, 1),
            "generation": round(generation, 1),
            "temperature": round(temperature, 2),
            "wind_speed": round(wind_speed, 2),
            "cloud_cover": cloud_cover,
            "buy_price": round(buy_price, 2),
            "sell_price": round(sell_price, 2),
            "main": self._get_weather_condition(cloud_cover),
        }

    def _get_base_consumption(self, hour):
        """Zwraca bazowe zużycie energii dla danej godziny."""
        if hour >= 22 or hour < 6:  # Noc
            return 600
        elif 6 <= hour < 9:  # Poranny szczyt
            return 1000
        elif 9 <= hour < 17:  # Dzień
            return 800
        elif 17 <= hour < 22:  # Wieczorny szczyt
            return 1200
        return 800

    def _get_base_generation(self, hour):
        """Zwraca bazową generację energii dla danej godziny."""
        if hour >= 22 or hour < 6:  # Noc
            return 0
        elif 6 <= hour < 9:  # Wzrost poranny
            return 400 * ((hour - 6) / 3.0)
        elif 9 <= hour < 17:  # Szczyt dzienny
            return 800
        elif 17 <= hour < 22:  # Spadek wieczorny
            return 400 * (1 - ((hour - 17) / 5.0))
        return 0

    def _get_base_temperature(self, hour):
        """Zwraca bazową temperaturę dla danej godziny."""
        if hour >= 22 or hour < 6:  # Noc
            return 15
        elif 6 <= hour < 12:  # Wzrost poranny
            return 15 + ((hour - 6) * 1.5)
        elif 12 <= hour < 17:  # Szczyt dzienny
            return 24
        elif 17 <= hour < 22:  # Spadek wieczorny
            return 24 - ((hour - 17) * 1.8)
        return 15

    def _get_weather_condition(self, cloud_cover):
        """Zwraca warunki pogodowe na podstawie zachmurzenia."""
        if cloud_cover < 20:
            return "Clear"
        elif cloud_cover < 50:
            return "Partly Cloudy"
        return "Cloudy"

    def start():
        base_dir = r"C:\Data\Energy"  # Dostosuj ścieżkę
        generator = DataGenerator(base_dir)

        # Generuj dane dla zakresu dat
        start_date = datetime(2024, 2, 1)
        days = 29

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            generator.generate_five_minute_data(current_date)


DataGenerator.start()
