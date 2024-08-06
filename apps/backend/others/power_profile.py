import calendar
import json
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from sklearn.preprocessing import StandardScaler
from scipy.signal import find_peaks
import os


from apps.backend.others import weather_data


class PowerProfile:
    def __init__(self, info_logger, error_logger, aggregation_interval=5):
        self.aggregation_interval = aggregation_interval
        self.data_buffer = []
        self.daily_profiles = {}
        self.consumption_data = []
        self.generation_data = []
        self.last_aggregation_time = None
        self.metadata = {"last_update": None, "day_count": 0, "holidays": []}
        self.scaler = StandardScaler()

        self.info_logger = info_logger
        self.error_logger = error_logger

        self.weather_data = weather_data

    def add_data_point(
        self, timestamp, consumption, generation, temperature, buy_price, sell_price
    ):
        self.data_buffer.append(
            {
                "timestamp": timestamp,
                "consumption": consumption,
                "generation": generation,
                "temperature": temperature,
                "buy_price": buy_price,
                "sell_price": sell_price,
            }
        )

        if self.should_aggregate():
            self.aggregate_data()

    def should_aggregate(self):
        if not self.last_aggregation_time:
            should_agg = len(self.data_buffer) >= 10
        else:
            current_time = datetime.now()
            time_since_last_aggregation = (
                current_time - self.last_aggregation_time
            ).total_seconds()
            should_agg = time_since_last_aggregation >= 300  # 300 sekund = 5 minut

        print(
            f"Should aggregate: {should_agg}, Buffer size: {len(self.data_buffer)}, Time since last aggregation: {time_since_last_aggregation if self.last_aggregation_time else 'N/A'}"
        )
        return should_agg

    def aggregate_data(self):
        if not self.data_buffer:
            print("Data buffer is empty, skipping aggregation")
            return

        aggregation_time = self.data_buffer[-1]["timestamp"].replace(
            minute=self.data_buffer[-1]["timestamp"].minute // 5 * 5,
            second=0,
            microsecond=0,
        )

        avg_consumption = round(
            sum(d["consumption"] for d in self.data_buffer) / len(self.data_buffer), 2
        )
        avg_generation = round(
            sum(d["generation"] for d in self.data_buffer) / len(self.data_buffer), 2
        )
        avg_temperature = round(
            sum(d["temperature"] for d in self.data_buffer) / len(self.data_buffer), 2
        )
        avg_buy_price = round(
            sum(d["buy_price"] for d in self.data_buffer) / len(self.data_buffer), 2
        )
        avg_sell_price = round(
            sum(d["sell_price"] for d in self.data_buffer) / len(self.data_buffer), 2
        )

        self.consumption_data.append(
            {"timestamp": aggregation_time.isoformat(), "consumption": avg_consumption}
        )
        self.generation_data.append(
            {"timestamp": aggregation_time.isoformat(), "generation": avg_generation}
        )

        print(
            f"Data aggregated at {aggregation_time}. Consumption data points: {len(self.consumption_data)}, Generation data points: {len(self.generation_data)}"
        )

        date_key = aggregation_time.date().isoformat()
        if date_key not in self.daily_profiles:
            self.daily_profiles[date_key] = {
                "date": date_key,
                "day_of_week": aggregation_time.strftime("%A"),
                "day_type": "deficit",  # To będzie aktualizowane o 23:55
                "consumption": [],
                "generation": [],
                "temperature": [],
                "buy_price": [],
                "sell_price": [],
                "surplus_deficit": [],
                "is_holiday": self.is_holiday(aggregation_time.date()),
                "season": self.get_season(aggregation_time),
            }
            self.metadata["day_count"] += 1

        self.daily_profiles[date_key]["consumption"].append(avg_consumption)
        self.daily_profiles[date_key]["generation"].append(avg_generation)
        self.daily_profiles[date_key]["temperature"].append(avg_temperature)
        self.daily_profiles[date_key]["buy_price"].append(avg_buy_price)
        self.daily_profiles[date_key]["sell_price"].append(avg_sell_price)
        self.daily_profiles[date_key]["surplus_deficit"].append(
            round(avg_generation - avg_consumption, 2)
        )

        self.last_aggregation_time = datetime.now()
        self.metadata["last_update"] = self.last_aggregation_time.isoformat()

        current_time = datetime.now()
        if current_time.hour == 23 and current_time.minute >= 55:
            self.update_day_type(current_time.date())

        self.data_buffer.clear()
        print(
            f"Data aggregated for {date_key}. Total data points: {len(self.daily_profiles[date_key]['consumption'])}"
        )

    def clear_weekly_data(self):
        self.consumption_data = []
        self.generation_data = []

    def clear_monthly_data(self):
        self.daily_profiles = {}

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

    def analyze_trends(self, start_date, end_date):
        trend_data = {"consumption": [], "generation": [], "surplus_deficit": []}

        current_date = start_date
        while current_date <= end_date:
            if current_date.isoformat() in self.daily_profiles:
                profile = self.daily_profiles[current_date.isoformat()]
                trend_data["consumption"].append(sum(profile["consumption"]))
                trend_data["generation"].append(sum(profile["generation"]))
                trend_data["surplus_deficit"].append(sum(profile["surplus_deficit"]))

            current_date += timedelta(days=1)

        # Sprawdź, czy mamy wystarczającą ilość danych do analizy
        if len(trend_data["consumption"]) < 2:
            return {
                "avg_daily_consumption": (
                    np.mean(trend_data["consumption"])
                    if trend_data["consumption"]
                    else 0
                ),
                "avg_daily_generation": (
                    np.mean(trend_data["generation"]) if trend_data["generation"] else 0
                ),
                "consumption_trend": 0,
                "generation_trend": 0,
                "surplus_deficit_trend": 0,
                "data_points": len(trend_data["consumption"]),
            }

        return {
            "avg_daily_consumption": round(np.mean(trend_data["consumption"]), 2),
            "avg_daily_generation": round(np.mean(trend_data["generation"]), 2),
            "consumption_trend": round(
                np.polyfit(
                    range(len(trend_data["consumption"])), trend_data["consumption"], 1
                )[0],
                2,
            ),
            "generation_trend": round(
                np.polyfit(
                    range(len(trend_data["generation"])), trend_data["generation"], 1
                )[0],
                2,
            ),
            "surplus_deficit_trend": round(
                np.polyfit(
                    range(len(trend_data["surplus_deficit"])),
                    trend_data["surplus_deficit"],
                    1,
                )[0],
                2,
            ),
            "data_points": len(trend_data["consumption"]),
        }

    def standardize_data(self, data):
        if len(data) < 2:
            print(
                f"Not enough data to standardize. Returning list of zeros. Data length: {len(data)}"
            )
            return [0] * len(data)
        standardized = (
            self.scaler.fit_transform(np.array(data).reshape(-1, 1)).flatten().tolist()
        )
        print(
            f"Data standardized. Original length: {len(data)}, Standardized length: {len(standardized)}"
        )
        return standardized

    def calculate_geometric_indicators(self, profile):
        if len(profile) < 4:
            return {
                "sum": round(np.sum(profile), 2),
                "peak_value": round(np.max(profile), 2) if profile.size > 0 else 0,
                "standard_deviation": "Insufficient data",
                "kurtosis": "Insufficient data",
            }
        kurtosis = stats.kurtosis(profile)
        return {
            "sum": round(np.sum(profile), 2),
            "peak_value": round(np.max(profile), 2),
            "standard_deviation": round(np.std(profile), 2),
            "kurtosis": (
                round(kurtosis, 2) if not np.isnan(kurtosis) else "Insufficient data"
            ),
        }

    def detect_patterns(self, profile, prominence=1):
        if len(profile) < 4:  # Potrzebujemy co najmniej 4 punktów do wykrycia wzorców
            return {"peak_indices": [], "peak_values": [], "peak_times": []}
        peaks, _ = find_peaks(profile, prominence=prominence)
        return {
            "peak_indices": peaks.tolist(),
            "peak_values": [profile[i] for i in peaks],
            "peak_times": [
                f"{i // 12:02d}:{(i % 12) * 5:02d}" for i in peaks
            ],  # Zakładając 5-minutowe interwały
        }

    def analyze_profile(self, date):
        if date.isoformat() not in self.daily_profiles:
            return None

        profile = self.daily_profiles[date.isoformat()]
        consumption = np.array(profile["consumption"])
        generation = np.array(profile["generation"])

        return {
            "date": date.isoformat(),
            "day_of_week": profile["day_of_week"],
            "consumption": {
                "raw": consumption.tolist(),
                "standardized": self.standardize_data(consumption),
                "geometric_indicators": self.calculate_geometric_indicators(
                    consumption
                ),
                "patterns": self.detect_patterns(consumption),
            },
            "generation": {
                "raw": generation.tolist(),
                "standardized": self.standardize_data(generation),
                "geometric_indicators": self.calculate_geometric_indicators(generation),
                "patterns": self.detect_patterns(generation),
            },
        }

    def save_data(self, filename_prefix):
        try:
            current_date = datetime.now()
            date_str = current_date.strftime("%Y%m%d")
            files_saved = []

            # Zapisywanie danych consumption i generation
            for data_type in ["consumption", "generation"]:
                filename = f"{filename_prefix}_{data_type}.json"

                if os.path.exists(filename):
                    with open(filename, "r") as f:
                        existing_data = json.load(f)
                else:
                    existing_data = []

                new_data = getattr(self, f"{data_type}_data")
                combined_data = self.round_dict_values(existing_data + new_data)

                with open(filename, "w") as f:
                    json.dump(combined_data, f, indent=2)
                files_saved.append(filename)

            # Zapisywanie daily_profiles
            daily_profiles_file = f"{filename_prefix}_daily_profiles.json"
            if os.path.exists(daily_profiles_file):
                with open(daily_profiles_file, "r") as f:
                    existing_profiles = json.load(f)
            else:
                existing_profiles = {}

            combined_profiles = self.round_dict_values(
                {**existing_profiles, **self.daily_profiles}
            )
            with open(daily_profiles_file, "w") as f:
                json.dump(combined_profiles, f, indent=2)
            files_saved.append(daily_profiles_file)

            # Zapisywanie metadata
            metadata_file = f"{filename_prefix}_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
            files_saved.append(metadata_file)

            # Tworzenie i zapisywanie pliku analizy
            analysis_file = f"{filename_prefix}_analysis.json"
            analysis_data = {}
            for date, profile in self.daily_profiles.items():
                analysis_data[date] = self.analyze_profile(
                    datetime.fromisoformat(date).date()
                )

            analysis_data = self.round_dict_values(analysis_data)
            with open(analysis_file, "w") as f:
                json.dump(analysis_data, f, indent=2)
            files_saved.append(analysis_file)

            self.info_logger.info(f"Files saved: {', '.join(files_saved)}")

            # Sprawdzenie końca tygodnia i miesiąca
            is_end_of_week = (
                current_date.weekday() == 6
                and current_date.hour == 23
                and current_date.minute >= 55
            )
            is_end_of_month = (
                current_date.day
                == calendar.monthrange(current_date.year, current_date.month)[1]
                and current_date.hour == 23
                and current_date.minute >= 55
            )

            return {
                "files_saved": files_saved,
                "is_end_of_week": is_end_of_week,
                "is_end_of_month": is_end_of_month,
            }

        except Exception as e:
            self.error_logger.error(f"Error saving data: {str(e)}")
            raise

    @classmethod
    def load_data(cls, filename_prefix, date_str):
        profile = cls()
        try:
            with open(f"{filename_prefix}_{date_str}_consumption.json", "r") as f:
                profile.consumption_data = json.load(f)

            with open(f"{filename_prefix}_{date_str}_generation.json", "r") as f:
                profile.generation_data = json.load(f)

            with open(f"{filename_prefix}_{date_str}_daily_profiles.json", "r") as f:
                profile.daily_profiles = json.load(f)

            with open(f"{filename_prefix}_{date_str}_metadata.json", "r") as f:
                profile.metadata = json.load(f)
        except FileNotFoundError:
            print(
                f"No existing profile data found for date {date_str}. Starting with a new profile."
            )
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON data: {e}")
        except IOError as e:
            print(f"Error reading data files: {e}")

        return profile

    def detect_anomalies(self, date, threshold=2):
        if date.isoformat() not in self.daily_profiles:
            return None

        profile = self.daily_profiles[date.isoformat()]
        consumption = np.array(profile["consumption"])
        generation = np.array(profile["generation"])

        consumption_mean = round(np.mean(consumption), 2)
        consumption_std = round(np.std(consumption), 2)
        generation_mean = round(np.mean(generation), 2)
        generation_std = round(np.std(generation), 2)

        consumption_anomalies = np.where(
            np.abs(consumption - consumption_mean) > threshold * consumption_std
        )[0]
        generation_anomalies = np.where(
            np.abs(generation - generation_mean) > threshold * generation_std
        )[0]

        return {
            "consumption_anomalies": consumption_anomalies.tolist(),
            "generation_anomalies": generation_anomalies.tolist(),
        }

    def is_holiday(self, date):
        # Tu powinna być logika sprawdzania świąt
        # Na razie zwracamy False
        return False

    def update_day_type(self, date):
        date_key = date.isoformat()
        if date_key in self.daily_profiles:
            surplus_deficit = self.daily_profiles[date_key]["surplus_deficit"]
            surplus_count = sum(1 for value in surplus_deficit if value > 0)
            deficit_count = sum(1 for value in surplus_deficit if value < 0)
            self.daily_profiles[date_key]["day_type"] = (
                "surplus" if surplus_count > deficit_count else "deficit"
            )
            self.info_logger.info(
                f"Updated day type for {date_key}: {self.daily_profiles[date_key]['day_type']}"
            )
        else:
            self.error_logger.error(f"No data found for date {date_key}")

    def archive_data(self, source_file, archive_file):
        if os.path.exists(source_file):
            with open(source_file, "r") as f:
                data = json.load(f)
            with open(archive_file, "w") as f:
                json.dump(data, f, indent=2)
            self.info_logger.info(f"Data archived from {source_file} to {archive_file}")
        else:
            self.error_logger.warning(
                f"Source file {source_file} does not exist. Nothing to archive."
            )

    def round_dict_values(self, d, decimal_places=2):
        if isinstance(d, dict):
            return {k: self.round_dict_values(v, decimal_places) for k, v in d.items()}
        elif isinstance(d, list):
            return [self.round_dict_values(v, decimal_places) for v in d]
        elif isinstance(d, float):
            return round(d, decimal_places)
        else:
            return d

    def predict_events(self):
        events = []
        forecast = self.weather_data.get_forecast()

        for _, row in forecast.iterrows():
            weather_id = row["id"]
            weather_main = row["main"]
            weather_description = row["description"]

            if weather_id // 100 == 2:  # Kody burz zaczynają się od 2xx
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

            # Sprawdzamy również ekstremalne temperatury
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
