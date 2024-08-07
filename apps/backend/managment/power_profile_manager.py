from datetime import datetime
from apps.backend.others.power_profile import PowerProfile
from apps.backend.managment.data_manager import DataManager
from apps.backend.others.weather_data import WeatherData


class PowerProfileManager:
    def __init__(
        self, power_profile_path, info_logger, error_logger, api_key, lat, lon
    ):
        self.power_profile = PowerProfile(info_logger, error_logger)
        self.data_manager = DataManager(power_profile_path)
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.last_30s_update = None
        self.last_5min_aggregation = None
        self.last_15min_weather_update = None
        self.last_3h_forecast_update = None
        self.weather_data = WeatherData(api_key=api_key, lat=lat, lon=lon)

    def update(self, current_time, consumption, generation, buy_price, sell_price):
        try:
            if self.should_update_weather(current_time):
                self.update_weather_data()

            weather_data = self.weather_data.get_current_weather()
            self.power_profile.add_data_point(
                current_time,
                consumption,
                generation,
                weather_data["temperature"],
                weather_data["wind_speed"],
                weather_data["clouds"],
                weather_data["main"],
                buy_price,
                sell_price,
            )

            if self.should_aggregate_5min(current_time):
                self.aggregate_and_log_5min_data()

            if self.should_update_forecast(current_time):
                self.update_weather_forecast()

        except Exception as e:
            self.error_logger.error(f"Error updating power profile: {str(e)}")

    def update_30s_data(
        self, current_time, consumption, generation, buy_price, sell_price
    ):
        weather_data = self.weather_data.get_current_weather()
        self.power_profile.add_data_point(
            current_time,
            consumption,
            generation,
            weather_data["temperature"],
            weather_data["wind_speed"],
            weather_data["clouds"],
            weather_data["main"],
            buy_price,
            sell_price,
        )
        self.last_30s_update = current_time

    def update_weather_data(self):
        try:
            current_weather = self.weather_data.get_current_weather()
            self.power_profile.current_weather = current_weather
            self.last_15min_weather_update = datetime.now()
            self.info_logger.info(
                f"Weather data updated at {self.last_15min_weather_update}"
            )
        except Exception as e:
            self.error_logger.error(f"Error updating weather data: {str(e)}")

    def update_weather_forecast(self):
        try:
            forecast = self.weather_data.get_forecast()
            self.power_profile.forecast = forecast
            self.last_3h_forecast_update = datetime.now()
            self.info_logger.info(
                f"Weather forecast updated at {self.last_3h_forecast_update}"
            )
        except Exception as e:
            self.error_logger.error(f"Error updating weather forecast: {str(e)}")

    def predict_events(self):
        events = []
        forecast = self.weather_data.get_forecast()

        for _, row in forecast.iterrows():
            weather_main = row["main"]
            weather_description = row["description"]

            if weather_main == "Thunderstorm":
                events.append(
                    {
                        "time": row["time"],
                        "event": "Thunderstorm",
                        "description": f"Possible power outage, activate off-grid mode. Details: {weather_description}",
                    }
                )
            elif row["wind_speed"] > 10:  # prędkość wiatru w m/s
                events.append(
                    {
                        "time": row["time"],
                        "event": "High wind",
                        "description": f'Potential for increased wind power generation. Wind speed: {row["wind_speed"]} m/s',
                    }
                )
            elif weather_main in ["Rain", "Snow"]:
                events.append(
                    {
                        "time": row["time"],
                        "event": "Precipitation",
                        "description": f"Possible reduction in solar power generation. Type: {weather_main}",
                    }
                )
            elif row["clouds"] > 70:  # Zachmurzenie powyżej 70%
                events.append(
                    {
                        "time": row["time"],
                        "event": "High cloud cover",
                        "description": f'Potential reduction in solar power generation. Cloud cover: {row["clouds"]}%',
                    }
                )

            if row["temperature"] > 35:  # Temperatura powyżej 35°C
                events.append(
                    {
                        "time": row["time"],
                        "event": "High temperature",
                        "description": f'Potential increase in energy demand for cooling. Temperature: {row["temperature"]}°C',
                    }
                )
            elif row["temperature"] < 0:  # Temperatura poniżej 0°C
                events.append(
                    {
                        "time": row["time"],
                        "event": "Low temperature",
                        "description": f'Potential increase in energy demand for heating. Temperature: {row["temperature"]}°C',
                    }
                )

        return events

    def should_aggregate_5min(self, current_time):
        return (
            self.last_5min_aggregation is None
            or (current_time - self.last_5min_aggregation).total_seconds() >= 300
        )

    def should_update_weather(self, current_time):
        return (
            self.last_15min_weather_update is None
            or (current_time - self.last_15min_weather_update).total_seconds() >= 900
        )

    def should_update_forecast(self, current_time):
        return (
            self.last_3h_forecast_update is None
            or (current_time - self.last_3h_forecast_update).total_seconds() >= 10800
        )

    def aggregate_and_log_5min_data(self):
        aggregated_data = self.power_profile.aggregate_5min_data()
        current_date = datetime.now().date()
        self.data_manager.save_detailed_data(current_date, aggregated_data)
        self.last_5min_aggregation = datetime.now()
        self.info_logger.info(
            f"5-minute data aggregated and logged at {self.last_5min_aggregation}"
        )

    def detect_and_log_anomalies(self):
        today = datetime.now().date()
        anomalies = self.power_profile.detect_anomalies(
            self.power_profile.aggregate_hourly_data()
        )
        if anomalies:
            self.info_logger.warning(f"Detected anomalies for {today}: {anomalies}")

    def get_temperature(self):
        return self.power_profile.weather_data.get_current_weather()["temperature"]

    def get_daily_profile(self, date):
        daily_profile = self.power_profile.create_daily_profile(date)
        daily_profile["predictions"] = self.predict_events()
        return daily_profile
