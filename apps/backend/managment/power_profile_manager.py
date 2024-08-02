from datetime import datetime, timedelta
from apps.backend.others.power_profile import PowerProfile


class PowerProfileManager:
    def __init__(self, power_profile_path, info_logger, error_logger):
        self.power_profile = PowerProfile(aggregation_interval=5)
        self.power_profile_path = power_profile_path
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.last_save_time = None

    def update(self, current_time, consumption, generation, buy_price, sell_price):
        self.info_logger.info(f"############Updating power profile at {current_time}")
        self.info_logger.info(
            f"########Current consumption: {consumption}, generation: {generation}"
        )
        temperature = self.get_temperature()
        self.power_profile.add_data_point(
            current_time, consumption, generation, temperature, buy_price, sell_price
        )

        if self.should_save_and_analyze():
            self.info_logger.info("Starting save and analyze process")
            self.save_and_analyze()
        else:
            self.info_logger.info("Not time to save and analyze yet")

    def should_save_and_analyze(self):
        if not self.last_save_time:
            return True
        time_since_last_save = (datetime.now() - self.last_save_time).total_seconds()
        result = time_since_last_save >= 300  # 300 sekund = 5 minut
        self.info_logger.info(f"################Should save and analyze: {result}")
        return result

    def save_and_analyze(self):
        self.info_logger.info("##########Starting save and analyze process")
        try:
            self.info_logger.info("###########Saving power profile")
            self.save_power_profile()
            self.info_logger.info("##############Power profile saved successfully")

            self.info_logger.info("######################Analyzing trends")
            self.analyze_and_log_trends()
            self.info_logger.info("################Trends analysis completed")

            self.info_logger.info("#############Detecting anomalies")
            self.detect_and_log_anomalies()
            self.info_logger.info("############Anomaly detection completed")

            self.last_save_time = datetime.now()
            self.info_logger.info(
                f"###########Save and analyze completed at {self.last_save_time}"
            )
        except Exception as e:
            self.error_logger.error(f"########Error in save_and_analyze: {str(e)}")
            self.error_logger.exception("########Full traceback:")

    def save_power_profile(self):
        self.power_profile.save_data(self.power_profile_path)
        self.info_logger.info("Power profile data saved")

    def analyze_and_log_trends(self):
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        trends = self.power_profile.analyze_trends(start_date, end_date)

        if trends["data_points"] < 2:
            self.info_logger.warning(
                f"Not enough data for trend analysis. Only {trends['data_points']} data points available."
            )
        else:
            self.info_logger.info(f"Weekly trends: {trends}")

    def detect_and_log_anomalies(self):
        today = datetime.now().date()
        anomalies = self.power_profile.detect_anomalies(today)
        if anomalies:
            self.info_logger.warning(f"Detected anomalies for {today}: {anomalies}")

    def load_power_profile(self, date_str):
        self.power_profile = PowerProfile.load_data(self.power_profile_path, date_str)
        self.info_logger.info(f"Power profile data loaded for {date_str}")

    def get_temperature(self):
        # Ta metoda powinna być zaimplementowana do pobierania aktualnej temperatury
        # Na razie zwracamy przykładową wartość
        return 20.0
