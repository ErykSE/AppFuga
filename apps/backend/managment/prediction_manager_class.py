from datetime import datetime, timedelta
import logging
import random


class PredictionManager:
    """
    Klasa, która będzie wykorzystywana w przyszłości. Będą tu metdody predykcyjne, bazujące na pogodzie, cenie energii i informacji o zachowaniu modelu.
    """

    def __init__(self, config):
        self.config = (
            config  # Konfiguracja zawierająca np. adresy API, klucze dostępu itp.
        )
        self.logger = logging.getLogger(__name__)

    def generate_mock_price_forecast(self):
        current_time = datetime.now()
        price_forecast = {}
        base_price = random.uniform(0.08, 0.12)  # Bazowa cena między 0.08 a 0.12
        for i in range(24):
            time = current_time + timedelta(hours=i)
            # Symulacja zmian cen w ciągu dnia
            if 6 <= time.hour < 10 or 17 <= time.hour < 21:
                price = base_price * random.uniform(
                    1.1, 1.3
                )  # Wyższe ceny w godzinach szczytu
            else:
                price = base_price * random.uniform(0.9, 1.1)
            price_forecast[time] = round(price, 4)
        return price_forecast

    def generate_mock_weather_forecast(self):
        current_time = datetime.now()
        weather_conditions = ["sunny", "cloudy", "rainy"]
        weather_forecast = {}
        for i in range(24):
            time = current_time + timedelta(hours=i)
            weather_forecast[time] = random.choice(weather_conditions)
        return weather_forecast

    def generate_mock_generation_forecast(self, weather_forecast):
        generation_forecast = {}
        for time, weather in weather_forecast.items():
            if weather == "sunny":
                generation_forecast[time] = random.uniform(80, 100)
            elif weather == "cloudy":
                generation_forecast[time] = random.uniform(40, 60)
            else:  # rainy
                generation_forecast[time] = random.uniform(20, 40)
        return generation_forecast

    def generate_mock_consumption_forecast(self):
        current_time = datetime.now()
        consumption_forecast = {}
        for i in range(24):
            time = current_time + timedelta(hours=i)
            if 8 <= time.hour < 20:  # Dzień
                consumption_forecast[time] = random.uniform(60, 100)
            else:  # Noc
                consumption_forecast[time] = random.uniform(30, 50)
        return consumption_forecast

    def prepare_predictions(self):
        weather_forecast = self.generate_mock_weather_forecast()
        predictions = {
            "price_forecast": self.generate_mock_price_forecast(),
            "weather_forecast": weather_forecast,
            "generation_forecast": self.generate_mock_generation_forecast(
                weather_forecast
            ),
            "consumption_forecast": self.generate_mock_consumption_forecast(),
        }
        print(f"Generated predictions: {predictions}")
        return predictions


"""

    def get_price_forecast(self):
        try:
            # Tutaj logika pobierania prognoz cen
            response = requests.get(self.config["price_api_url"])
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(
                    f"Failed to get price forecast. Status code: {response.status_code}"
                )
                return {}
        except Exception as e:
            self.logger.error(f"Error in get_price_forecast: {str(e)}")
            return {}

    def get_weather_forecast(self):
        try:
            # Tutaj logika pobierania prognoz pogody
            response = requests.get(self.config["weather_api_url"])
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(
                    f"Failed to get weather forecast. Status code: {response.status_code}"
                )
                return {}
        except Exception as e:
            self.logger.error(f"Error in get_weather_forecast: {str(e)}")
            return {}

    def estimate_generation(self, weather_forecast):
        try:
            # Tutaj logika szacowania generacji na podstawie prognozy pogody
            # To jest uproszczony przykład - w rzeczywistości byłoby to bardziej skomplikowane
            generation_forecast = {}
            for time, weather in weather_forecast.items():
                if weather == "sunny":
                    generation_forecast[time] = 100  # 100 kW w słoneczny dzień
                elif weather == "cloudy":
                    generation_forecast[time] = 50  # 50 kW w pochmurny dzień
                else:
                    generation_forecast[time] = 20  # 20 kW w inne dni
            return generation_forecast
        except Exception as e:
            self.logger.error(f"Error in estimate_generation: {str(e)}")
            return {}

    def predict_consumption(self):
        try:
            # Tutaj logika przewidywania zużycia
            # To może być bardziej skomplikowane, uwzględniające historyczne dane, dzień tygodnia itp.
            current_time = datetime.now()
            consumption_forecast = {}
            for i in range(24):
                time = current_time + timedelta(hours=i)
                if 8 <= time.hour < 20:  # Dzień
                    consumption_forecast[time] = 80  # 80 kW w ciągu dnia
                else:  # Noc
                    consumption_forecast[time] = 40  # 40 kW w nocy
            return consumption_forecast
        except Exception as e:
            self.logger.error(f"Error in predict_consumption: {str(e)}")
            return {}

    def prepare_predictions(self):
        weather_forecast = self.get_weather_forecast()
        return {
            "price_forecast": self.get_price_forecast(),
            "weather_forecast": weather_forecast,
            "generation_forecast": self.estimate_generation(weather_forecast),
            "consumption_forecast": self.predict_consumption(),
        }

"""
