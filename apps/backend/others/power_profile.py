# import calendar
# import json
from datetime import datetime, timedelta
import numpy as np
from scipy import stats

# from sklearn.preprocessing import StandardScaler
# from scipy.signal import find_peaks
# import os
import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose
from sklearn.ensemble import IsolationForest
from datetime import timedelta
from apps.backend.others.weather_data import WeatherData


class PowerProfile:
    def __init__(self, info_logger, error_logger, aggregation_interval=5):
        self.current_data = pd.DataFrame()
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.isolation_forest = IsolationForest(contamination=0.1)
        self.current_weather = None
        self.forecast = None

    def add_data_point(
        self,
        timestamp,
        consumption,
        generation,
        temperature,
        wind_speed,
        cloud_cover,
        main,
        buy_price,
        sell_price,
    ):
        new_data = pd.DataFrame(
            {
                "timestamp": [timestamp],
                "consumption": [float(consumption)],
                "generation": [float(generation)],
                "temperature": [float(temperature)],
                "wind_speed": [float(wind_speed)],
                "cloud_cover": [float(cloud_cover)],
                "main": [str(main)],
                "buy_price": [float(buy_price)],
                "sell_price": [float(sell_price)],
            }
        )
        self.current_data = pd.concat([self.current_data, new_data], ignore_index=True)

    def aggregate_5min_data(self):
        if self.current_data.empty:
            return pd.DataFrame()

        self.info_logger.debug(f"Current data types: {self.current_data.dtypes}")
        self.info_logger.debug(f"Current data head: {self.current_data.head()}")

        # Konwertuj kolumny numeryczne na float
        numeric_columns = [
            "consumption",
            "generation",
            "temperature",
            "wind_speed",
            "cloud_cover",
            "buy_price",
            "sell_price",
        ]
        for col in numeric_columns:
            if col in self.current_data.columns:
                self.current_data[col] = pd.to_numeric(
                    self.current_data[col], errors="coerce"
                )

        # Definiuj funkcje agregacji dla różnych typów kolumn
        agg_functions = {
            "consumption": "mean",
            "generation": "mean",
            "temperature": "mean",
            "wind_speed": "mean",
            "cloud_cover": "mean",
            "buy_price": "mean",
            "sell_price": "mean",
            "main": lambda x: (
                x.mode().iloc[0] if not x.empty else None
            ),  # Najczęstsza wartość dla 'main'
        }

        # Usuń kolumny, których nie ma w danych
        agg_functions = {
            k: v for k, v in agg_functions.items() if k in self.current_data.columns
        }

        return (
            self.current_data.resample("5min", on="timestamp")
            .agg(agg_functions)
            .reset_index()
        )

    def aggregate_hourly_data(self):
        if self.current_data.empty:
            return pd.DataFrame()
        return self.current_data.resample("H", on="timestamp").mean().reset_index()

    def create_daily_profile(self, date):
        day_data = self.current_data[self.current_data["timestamp"].dt.date == date]
        hourly_data = self.aggregate_hourly_data()

        daily_profile = {
            "date": date.isoformat(),
            "day_of_week": date.strftime("%A"),
            "is_weekend": date.weekday() >= 5,
            "season": self.get_season(date),
            "is_holiday": self.is_holiday(date),
            "weather_summary": self.calculate_weather_summary(hourly_data),
            "energy_summary": self.calculate_energy_summary(hourly_data),
            "hourly_data": hourly_data.to_dict("records"),
            "energy_sources": self.calculate_energy_sources(hourly_data),
            "energy_storage": self.get_energy_storage_data(date),
            "grid_interaction": self.calculate_grid_interaction(hourly_data),
            "anomalies": self.detect_anomalies(hourly_data),
            "efficiency_metrics": self.calculate_efficiency_metrics(hourly_data),
        }

        return daily_profile

    def get_season(self, date):
        month = date.month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"

    def is_holiday(self, date):
        # Tu powinna być logika sprawdzania świąt
        # Na razie zwracamy False
        return False

    def detect_anomalies(
        self, date, columns=["consumption", "generation"], threshold=-0.5
    ):
        data = self.get_data(date, date)  # Pobierz dane dla konkretnego dnia
        if data.empty:
            return {"error": "No data available for the specified date"}

        data = data[columns].copy()
        if len(data) < 2:
            return {"error": "Insufficient data for anomaly detection"}

        self.isolation_forest.fit(data)
        anomaly_labels = self.isolation_forest.predict(data)
        anomalies = data[anomaly_labels == -1]

        result = []
        for idx, row in anomalies.iterrows():
            result.append(
                {"timestamp": idx.isoformat(), "anomaly_values": row.to_dict()}
            )

        return result

    def analyze_trends(self, start_date, end_date):
        data = self.get_data(start_date, end_date)
        if data.empty:
            return {"error": "No data available for the specified date range"}

        result = {
            "summary": data.describe().to_dict(),
            "consumption_trend": self.calculate_trend(data, "consumption"),
            "generation_trend": self.calculate_trend(data, "generation"),
            "temperature_correlation": data["consumption"].corr(data["temperature"]),
            "wind_speed_correlation": data["generation"].corr(data["wind_speed"]),
            "cloud_cover_correlation": data["generation"].corr(data["cloud_cover"]),
        }

        # Dekompozycja sezonowa dla konsumpcji
        if len(data) > 24:  # Potrzebujemy co najmniej 2 dni danych
            try:
                decomposition = seasonal_decompose(
                    data["consumption"], model="additive", period=24
                )
                result["consumption_seasonal"] = {
                    "trend": decomposition.trend.dropna().to_dict(),
                    "seasonal": decomposition.seasonal.dropna().to_dict(),
                    "residual": decomposition.resid.dropna().to_dict(),
                }
            except Exception as e:
                result["consumption_seasonal"] = {"error": str(e)}

        # Autokorelacja
        result["consumption_autocorrelation"] = data["consumption"].autocorr(lag=24)
        result["generation_autocorrelation"] = data["generation"].autocorr(lag=24)

        return result

    def get_data(self, start_date, end_date):
        # Ta metoda powinna zwracać DataFrame z danymi z określonego zakresu dat
        # Implementacja zależy od sposobu przechowywania danych
        data = pd.DataFrame()
        current_date = start_date
        while current_date <= end_date:
            daily_data = self.data_manager.load_hourly_data(current_date)
            if daily_data is not None:
                data = pd.concat([data, daily_data])
            current_date += timedelta(days=1)
        return data

    def calculate_trend(self, data, column):
        # Implementacja obliczania trendu
        x = np.arange(len(data))
        y = data[column].values
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        return {
            "slope": slope,
            "intercept": intercept,
            "r_value": r_value,
            "p_value": p_value,
            "std_err": std_err,
        }

    def calculate_weather_summary(self, hourly_data):
        return {
            "average_temperature": hourly_data["temperature"].mean(),
            "max_temperature": hourly_data["temperature"].max(),
            "min_temperature": hourly_data["temperature"].min(),
            "average_wind_speed": hourly_data["wind_speed"].mean(),
            "max_wind_speed": hourly_data["wind_speed"].max(),
            "average_cloud_cover": hourly_data["cloud_cover"].mean(),
            "main_weather": (
                hourly_data["main"].mode().iloc[0]
                if not hourly_data["main"].empty
                else None
            ),
        }

    def calculate_energy_summary(self, hourly_data):
        return {
            "total_consumption": hourly_data["consumption"].sum(),
            "total_generation": hourly_data["generation"].sum(),
            "net_balance": hourly_data["generation"].sum()
            - hourly_data["consumption"].sum(),
            "peak_consumption": hourly_data["consumption"].max(),
            "peak_generation": hourly_data["generation"].max(),
            "peak_consumption_time": (
                hourly_data["consumption"].idxmax().strftime("%H:%M")
                if not hourly_data["consumption"].empty
                else None
            ),
            "peak_generation_time": (
                hourly_data["generation"].idxmax().strftime("%H:%M")
                if not hourly_data["generation"].empty
                else None
            ),
        }

    def calculate_energy_sources(self, hourly_data):
        # Zakładając, że mamy dane o różnych źródłach energii
        return {
            "solar": {
                "total_generation": hourly_data.get("solar_generation", 0).sum(),
                "peak_generation": hourly_data.get("solar_generation", 0).max(),
                "peak_time": (
                    hourly_data["solar_generation"].idxmax().strftime("%H:%M")
                    if "solar_generation" in hourly_data
                    else None
                ),
            },
            "wind": {
                "total_generation": hourly_data.get("wind_generation", 0).sum(),
                "peak_generation": hourly_data.get("wind_generation", 0).max(),
                "peak_time": (
                    hourly_data["wind_generation"].idxmax().strftime("%H:%M")
                    if "wind_generation" in hourly_data
                    else None
                ),
            },
            # Dodaj inne źródła energii, jeśli są dostępne
        }

    def get_energy_storage_data(self, date):
        # Zakładając, że mamy dostęp do danych o magazynie energii
        storage_data = self.data_manager.get_storage_data(
            date
        )  # Implementacja tej metody zależy od struktury danych
        if storage_data is not None:
            return {
                "current_level": storage_data.get("current_level", 0),
                "capacity": storage_data.get("capacity", 0),
                "charge_rate": storage_data.get("charge_rate", 0),
                "discharge_rate": storage_data.get("discharge_rate", 0),
            }
        return None

    def calculate_grid_interaction(self, hourly_data):
        return {
            "energy_imported": hourly_data.get("grid_import", 0).sum(),
            "energy_exported": hourly_data.get("grid_export", 0).sum(),
            "net_grid_interaction": hourly_data.get("grid_export", 0).sum()
            - hourly_data.get("grid_import", 0).sum(),
        }

    def calculate_efficiency_metrics(self, hourly_data):
        total_consumption = hourly_data["consumption"].sum()
        total_generation = hourly_data["generation"].sum()
        grid_import = hourly_data.get("grid_import", 0).sum()

        self_consumption = min(total_consumption, total_generation)
        self_consumption_ratio = (
            self_consumption / total_generation if total_generation > 0 else 0
        )
        self_sufficiency_ratio = (
            self_consumption / total_consumption if total_consumption > 0 else 0
        )

        return {
            "self_consumption_ratio": self_consumption_ratio,
            "self_sufficiency_ratio": self_sufficiency_ratio,
            "overall_system_efficiency": (
                (total_generation - grid_import) / total_generation
                if total_generation > 0
                else 0
            ),
        }

    ####################################

    def get_5min_profile(self, date):
        day_data = self.current_data[self.current_data["timestamp"].dt.date == date]
        profile = {}
        for _, row in day_data.iterrows():
            time_key = row["timestamp"].strftime("%H:%M")
            profile[time_key] = {
                "consumption": row["consumption"],
                "generation": row["generation"],
                "temperature": row["temperature"],
                "wind_speed": row["wind_speed"],
                "cloud_cover": row["cloud_cover"],
            }
        return {date.isoformat(): profile}

    def get_hourly_profile(self, date):
        hourly_data = self.aggregate_hourly_data()
        hourly_data = hourly_data[hourly_data["timestamp"].dt.date == date]

        profile = {
            "hourly_data": {},
            "energy_summary": self.calculate_energy_summary(hourly_data),
            "weather_summary": self.calculate_weather_summary(hourly_data),
        }

        for _, row in hourly_data.iterrows():
            time_key = row["timestamp"].strftime("%H:%M")
            profile["hourly_data"][time_key] = {
                "consumption": row["consumption"],
                "generation": row["generation"],
                "temperature": row["temperature"],
                "wind_speed": row["wind_speed"],
                "cloud_cover": row["cloud_cover"],
            }

        return {date.isoformat(): profile}


"""
    def get_daily_profile(self, date):
        hourly_data = self.aggregate_hourly_data()
        hourly_data = hourly_data[hourly_data["timestamp"].dt.date == date]

        return {
            "date": date.isoformat(),
            "day_of_week": date.strftime("%A"),
            "is_weekend": date.weekday() >= 5,
            "season": self.get_season(date),
            "is_holiday": self.is_holiday(date),
            "weather_summary": self.calculate_weather_summary(hourly_data),
            "energy_summary": self.calculate_energy_summary(hourly_data),
            "hourly_data": [
                {
                    "hour": row["timestamp"].strftime("%H:%M"),
                    "consumption": row["consumption"],
                    "generation": row["generation"],
                    "temperature": row["temperature"],
                    "wind_speed": row["wind_speed"],
                    "cloud_cover": row["cloud_cover"],
                    "buy_price": row["buy_price"],
                    "sell_price": row["sell_price"],
                }
                for _, row in hourly_data.iterrows()
            ],
            "energy_sources": self.calculate_energy_sources(hourly_data),
            "energy_storage": self.get_energy_storage_data(date),
            "grid_interaction": self.calculate_grid_interaction(hourly_data),
            "anomalies": self.detect_anomalies(hourly_data),
            "predictions": self.predict_events(),
            "efficiency_metrics": self.calculate_efficiency_metrics(hourly_data),
        }
"""
