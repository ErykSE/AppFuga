import requests
from datetime import datetime, timedelta
import pandas as pd


class WeatherData:
    def __init__(self, api_key, lat, lon):
        self.api_key = api_key
        self.lat = lat
        self.lon = lon
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.current_weather = None
        self.forecast = None

    def update_current_weather(self):
        url = f"{self.base_url}/weather?lat={self.lat}&lon={self.lon}&appid={self.api_key}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            self.current_weather = {
                "id": data["weather"][0]["id"],
                "main": data["weather"][0]["main"],
                "description": data["weather"][0]["description"],
                "temperature": data["main"]["temp"],
                "wind_speed": data["wind"]["speed"],
                "clouds": data["clouds"]["all"],
            }
        else:
            raise Exception(f"Error fetching current weather: {response.status_code}")

    def update_forecast(self, hours=48):
        url = f"{self.base_url}/forecast?lat={self.lat}&lon={self.lon}&appid={self.api_key}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            forecast = []
            current_time = datetime.now()
            end_time = current_time + timedelta(hours=hours)
            for item in data["list"]:
                forecast_time = datetime.fromtimestamp(item["dt"])
                if current_time <= forecast_time <= end_time:
                    forecast.append(
                        {
                            "time": forecast_time,
                            "id": item["weather"][0]["id"],
                            "main": item["weather"][0]["main"],
                            "description": item["weather"][0]["description"],
                            "temperature": item["main"]["temp"],
                            "wind_speed": item["wind"]["speed"],
                            "clouds": item["clouds"]["all"],
                        }
                    )
            self.forecast = pd.DataFrame(forecast)
        else:
            raise Exception(f"Error fetching forecast: {response.status_code}")

    def get_current_weather(self):
        if self.current_weather is None:
            self.update_current_weather()
        return self.current_weather

    def get_forecast(self):
        if self.forecast is None:
            self.update_forecast()
        return self.forecast
