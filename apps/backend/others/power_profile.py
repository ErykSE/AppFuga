import json
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from sklearn.preprocessing import StandardScaler
from scipy.signal import find_peaks


class PowerProfile:
    def __init__(self, aggregation_interval=5):
        self.aggregation_interval = aggregation_interval
        self.data_buffer = []
        self.daily_profiles = {}
        self.consumption_data = []
        self.generation_data = []
        self.last_aggregation_time = None
        self.metadata = {"last_update": None, "day_count": 0, "holidays": []}
        self.scaler = StandardScaler()

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
        print(f"Data point added: {timestamp}, Buffer size: {len(self.data_buffer)}")

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

        avg_consumption = sum(d["consumption"] for d in self.data_buffer) / len(
            self.data_buffer
        )
        avg_generation = sum(d["generation"] for d in self.data_buffer) / len(
            self.data_buffer
        )
        avg_temperature = sum(d["temperature"] for d in self.data_buffer) / len(
            self.data_buffer
        )
        avg_buy_price = sum(d["buy_price"] for d in self.data_buffer) / len(
            self.data_buffer
        )
        avg_sell_price = sum(d["sell_price"] for d in self.data_buffer) / len(
            self.data_buffer
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
                "day_type": "deficit",  # This should be calculated based on actual data
                "consumption": [],
                "generation": [],
                "temperature": [],
                "buy_price": [],
                "sell_price": [],
                "surplus_deficit": [],
                "is_holiday": False,  # This should be determined based on actual data
                "season": self.get_season(aggregation_time),
            }
            self.metadata["day_count"] += 1

        self.daily_profiles[date_key]["consumption"].append(avg_consumption)
        self.daily_profiles[date_key]["generation"].append(avg_generation)
        self.daily_profiles[date_key]["temperature"].append(avg_temperature)
        self.daily_profiles[date_key]["buy_price"].append(avg_buy_price)
        self.daily_profiles[date_key]["sell_price"].append(avg_sell_price)
        self.daily_profiles[date_key]["surplus_deficit"].append(
            avg_generation - avg_consumption
        )

        self.last_aggregation_time = datetime.now()
        self.metadata["last_update"] = self.last_aggregation_time.isoformat()

        self.data_buffer.clear()
        print(
            f"Data aggregated for {date_key}. Total data points: {len(self.daily_profiles[date_key]['consumption'])}"
        )

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
            "avg_daily_consumption": np.mean(trend_data["consumption"]),
            "avg_daily_generation": np.mean(trend_data["generation"]),
            "consumption_trend": (
                np.polyfit(
                    range(len(trend_data["consumption"])), trend_data["consumption"], 1
                )[0]
                if len(trend_data["consumption"]) > 1
                else 0
            ),
            "generation_trend": (
                np.polyfit(
                    range(len(trend_data["generation"])), trend_data["generation"], 1
                )[0]
                if len(trend_data["generation"]) > 1
                else 0
            ),
            "surplus_deficit_trend": (
                np.polyfit(
                    range(len(trend_data["surplus_deficit"])),
                    trend_data["surplus_deficit"],
                    1,
                )[0]
                if len(trend_data["surplus_deficit"]) > 1
                else 0
            ),
            "data_points": len(trend_data["consumption"]),
        }

    def standardize_data(self, data):
        return self.scaler.fit_transform(np.array(data).reshape(-1, 1)).flatten()

    def calculate_geometric_indicators(self, profile):
        if len(profile) < 4:  # Potrzebujemy co najmniej 4 punktów do obliczenia kurtozy
            return {
                "sum": np.sum(profile),
                "peak_value": np.max(profile) if len(profile) > 0 else 0,
                "standard_deviation": np.std(profile) if len(profile) > 1 else 0,
                "kurtosis": "Insufficient data",
            }
        return {
            "sum": np.sum(profile),
            "peak_value": np.max(profile),
            "standard_deviation": np.std(profile),
            "kurtosis": stats.kurtosis(profile),
        }

    def detect_patterns(self, profile, prominence=1):
        peaks, _ = find_peaks(profile, prominence=prominence)
        return {
            "peak_indices": peaks.tolist(),
            "peak_values": [profile[i] for i in peaks],
            "peak_times": [f"{i // 4:02d}:{(i % 4) * 15:02d}" for i in peaks],
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
                "standardized": self.standardize_data(consumption).tolist(),
                "geometric_indicators": self.calculate_geometric_indicators(
                    consumption
                ),
                "patterns": self.detect_patterns(consumption),
            },
            "generation": {
                "raw": generation.tolist(),
                "standardized": self.standardize_data(generation).tolist(),
                "geometric_indicators": self.calculate_geometric_indicators(generation),
                "patterns": self.detect_patterns(generation),
            },
        }

    def save_data(self, filename_prefix):
        try:
            date_str = datetime.now().strftime("%Y%m%d")
            files_saved = []

            # Zapisywanie danych w oryginalnym formacie
            for data_type in [
                "consumption",
                "generation",
                "daily_profiles",
                "metadata",
            ]:
                filename = f"{filename_prefix}_{date_str}_{data_type}.json"
                with open(filename, "w") as f:
                    if data_type == "daily_profiles":
                        json.dump(self.daily_profiles, f, indent=2)
                    elif data_type == "metadata":
                        json.dump(self.metadata, f, indent=2)
                    else:
                        json.dump(getattr(self, f"{data_type}_data"), f, indent=2)
                files_saved.append(filename)

            # Zapisywanie analizy profilu
            analysis = {
                date: self.analyze_profile(datetime.strptime(date, "%Y-%m-%d").date())
                for date in self.daily_profiles.keys()
            }
            filename = f"{filename_prefix}_{date_str}_analysis.json"
            with open(filename, "w") as f:
                json.dump(analysis, f, indent=2)
            files_saved.append(filename)

            print(f"Files saved: {', '.join(files_saved)}")

            # Clear data after saving
            self.consumption_data = []
            self.generation_data = []
        except Exception as e:
            print(f"Error saving data: {str(e)}")
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

        consumption_mean = np.mean(consumption)
        consumption_std = np.std(consumption)
        generation_mean = np.mean(generation)
        generation_std = np.std(generation)

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
