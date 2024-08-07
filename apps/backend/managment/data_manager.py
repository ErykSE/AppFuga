import pandas as pd
import json
import os
from datetime import datetime, timedelta


class DataManager:
    def __init__(self, base_path):
        self.base_path = base_path
        self.ensure_directories()

    def ensure_directories(self):
        for dir_name in ["detailed", "hourly", "daily"]:
            os.makedirs(os.path.join(self.base_path, dir_name), exist_ok=True)

    def save_detailed_data(self, date, data):
        file_path = os.path.join(
            self.base_path, "detailed", f"{date.strftime('%Y-%m-%d')}.parquet"
        )
        df = pd.DataFrame(data)
        df.to_parquet(file_path, engine="pyarrow", compression="snappy")

    def save_hourly_data(self, date, data):
        file_path = os.path.join(
            self.base_path, "hourly", f"{date.strftime('%Y-%m-%d')}.json"
        )
        with open(file_path, "w") as f:
            json.dump(data, f)

    def save_daily_profile(self, date, profile):
        file_path = os.path.join(
            self.base_path, "daily", f"{date.strftime('%Y-%m-%d')}.json"
        )
        with open(file_path, "w") as f:
            json.dump(profile, f)

    def load_detailed_data(self, date):
        file_path = os.path.join(
            self.base_path, "detailed", f"{date.strftime('%Y-%m-%d')}.parquet"
        )
        try:
            return pd.read_parquet(file_path)
        except FileNotFoundError:
            print(f"No detailed data found for {date}")
            return pd.DataFrame()

    def load_hourly_data(self, date):
        file_path = os.path.join(
            self.base_path, "hourly", f"{date.strftime('%Y-%m-%d')}.json"
        )
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"No hourly data found for {date}")
            return {}

    def load_daily_profile(self, date):
        file_path = os.path.join(
            self.base_path, "daily", f"{date.strftime('%Y-%m-%d')}.json"
        )
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"No daily profile found for {date}")
            return {}

    def cleanup_old_data(self):
        today = datetime.now().date()
        self.remove_old_files("detailed", today - timedelta(days=90))
        self.remove_old_files("hourly", today - timedelta(days=365))
        self.remove_old_files("daily", today - timedelta(days=365 * 5))

    def remove_old_files(self, directory, cutoff_date):
        dir_path = os.path.join(self.base_path, directory)
        for filename in os.listdir(dir_path):
            file_date = datetime.strptime(filename.split(".")[0], "%Y-%m-%d").date()
            if file_date < cutoff_date:
                os.remove(os.path.join(dir_path, filename))

    def prepare_data_for_prediction(self, target_date, prediction_type):
        if prediction_type == "short_term":
            detailed_data = self.load_detailed_data(target_date)
            hourly_data = self.load_hourly_data(target_date - timedelta(days=1))

            # Przygotowanie danych dla modelu krótkoterminowego
            last_6_hours = detailed_data[
                detailed_data["timestamp"] >= (target_date - timedelta(hours=6))
            ]
            return {"detailed": last_6_hours.to_dict("records"), "hourly": hourly_data}

        elif prediction_type == "medium_term":
            # Przygotuj dane godzinowe z ostatnich 7 dni
            hourly_data = {}
            for i in range(7):
                date = target_date - timedelta(days=i)
                hourly_data[date.isoformat()] = self.load_hourly_data(date)

            return hourly_data

        elif prediction_type == "long_term":
            # Przygotuj profile dzienne z ostatnich 3 miesięcy
            daily_profiles = {}
            for i in range(90):
                date = target_date - timedelta(days=i)
                daily_profiles[date.isoformat()] = self.load_daily_profile(date)

            return daily_profiles

        else:
            raise ValueError(f"Unknown prediction type: {prediction_type}")
