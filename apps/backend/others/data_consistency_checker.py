import json
import time


class DataConsistencyChecker:
    def __init__(
        self, save_path, load_path, info_logger, error_logger, max_attempts=3, delay=5
    ):
        self.save_path = save_path
        self.load_path = load_path
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.max_attempts = max_attempts
        self.delay = delay

    def check_and_retry_consistency(self):
        for attempt in range(self.max_attempts):
            if self.check_consistency():
                return True

            self.info_logger.info(
                f"Retrying consistency check. Attempt {attempt + 1} of {self.max_attempts}"
            )
            self.push_to_database()  # Symulacja ponownego zapisu do bazy danych
            time.sleep(self.delay)

        return False

    def check_consistency(self):
        try:
            with open(self.save_path, "r") as f1, open(self.load_path, "r") as f2:
                saved_data = json.load(f1)
                loaded_data = json.load(f2)

            # Porównujemy tylko klucze, które są w live_data
            keys_to_compare = [
                "pv_panels",
                "wind_turbines",
                "fuel_turbines",
                "fuel_cells",
                "bess",
                "non_adjustable_devices",
                "adjustable_devices",
            ]

            is_consistent = all(
                saved_data.get(key) == loaded_data.get(key) for key in keys_to_compare
            )

            if is_consistent:
                self.info_logger.info("Data consistency check passed")
            else:
                self.error_logger.warning("Data consistency check failed")
            return is_consistent
        except Exception as e:
            self.error_logger.error(f"Error during consistency check: {str(e)}")
            return False

    def push_to_database(self):
        # Symulacja ponownego zapisu do bazy danych
        self.info_logger.info("Simulating push to database")
        # W przyszłości tutaj będzie faktyczna implementacja zapisu do bazy danych
        # Obecnie nie robimy nic, ponieważ dane są już zapisane w pliku
