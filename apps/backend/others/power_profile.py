import json
from datetime import datetime, timedelta


class PowerProfile:
    def __init__(self, data_points=96):  # 96 punktów dla 15-minutowych interwałów
        self.data_points = data_points
        self.consumption_profile = [0] * data_points
        self.generation_profile = [0] * data_points
        self.day_count = 0

    def update_profile(self, timestamp, consumption, generation):
        index = self._get_index_from_timestamp(timestamp)
        self.consumption_profile[index] = (
            (self.consumption_profile[index] * self.day_count) + consumption
        ) / (self.day_count + 1)
        self.generation_profile[index] = (
            (self.generation_profile[index] * self.day_count) + generation
        ) / (self.day_count + 1)

    def _get_index_from_timestamp(self, timestamp):
        minutes = timestamp.hour * 60 + timestamp.minute
        return (minutes // 15) % self.data_points

    def new_day(self):
        self.day_count += 1

    def save_to_file(self, filename):
        data = {
            "consumption_profile": self.consumption_profile,
            "generation_profile": self.generation_profile,
            "day_count": self.day_count,
            "last_update": datetime.now().isoformat(),
        }
        with open(filename, "w") as f:
            json.dump(data, f)

    @classmethod
    def load_from_file(cls, filename):
        with open(filename, "r") as f:
            data = json.load(f)
        profile = cls()
        profile.consumption_profile = data["consumption_profile"]
        profile.generation_profile = data["generation_profile"]
        profile.day_count = data["day_count"]
        return profile
