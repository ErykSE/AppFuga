from datetime import datetime, timedelta
import os
import shutil
from apps.backend.others.power_profile import PowerProfile


class PowerProfileManager:
    def __init__(self, power_profile_path, info_logger, error_logger):
        self.power_profile = PowerProfile(info_logger, error_logger)
        self.power_profile_path = power_profile_path
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.last_save_time = None

    def update(self, current_time, consumption, generation, buy_price, sell_price):
        try:
            self.info_logger.info(f"Updating power profile at {current_time}")
            self.info_logger.info(
                f"Current consumption: {consumption}, generation: {generation}"
            )
            temperature = self.get_temperature()
            self.power_profile.add_data_point(
                current_time,
                consumption,
                generation,
                temperature,
                buy_price,
                sell_price,
            )

            if self.should_save_and_analyze():
                self.save_and_archive()
        except Exception as e:
            self.error_logger.error(f"Error updating power profile: {str(e)}")

    def should_save_and_analyze(self, interval=300):  # 300 sekund = 5 minut
        if not self.last_save_time:
            return True
        time_since_last_save = (datetime.now() - self.last_save_time).total_seconds()
        return time_since_last_save >= interval

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

    def save_and_archive(self):
        try:
            save_result = self.power_profile.save_data(self.power_profile_path)
            self.analyze_and_log_trends()
            self.detect_and_log_anomalies()

            if save_result["is_end_of_week"]:
                self.archive_weekly_data()

            if save_result["is_end_of_month"]:
                self.archive_monthly_data()

            self.last_save_time = datetime.now()
            self.info_logger.info(
                f"Save and archive completed at {self.last_save_time}"
            )
        except Exception as e:
            self.error_logger.error(f"Error in save_and_archive: {str(e)}")
            self.error_logger.exception("Full traceback:")

    def archive_weekly_data(self):
        for data_type in ["consumption", "generation"]:
            source_file = f"{self.power_profile_path}_{data_type}.json"
            archive_file = f"{self.power_profile_path}_archive_weekly_{data_type}_{datetime.now().strftime('%Y%m%d')}.json"
            self.archive_file(source_file, archive_file)
        self.power_profile.clear_weekly_data()
        self.info_logger.info("Weekly data archived and buffers cleared")

    def archive_monthly_data(self):
        source_file = f"{self.power_profile_path}_daily_profiles.json"
        archive_file = f"{self.power_profile_path}_archive_monthly_daily_profiles_{datetime.now().strftime('%Y%m')}.json"
        self.archive_file(source_file, archive_file)
        self.power_profile.clear_monthly_data()
        self.info_logger.info("Monthly data archived and daily profiles cleared")

    def archive_file(self, source_file, archive_file):
        if os.path.exists(source_file):
            shutil.copy2(source_file, archive_file)
            open(source_file, "w").close()  # Clear the source file
            self.info_logger.info(f"Data archived from {source_file} to {archive_file}")
        else:
            self.error_logger.warning(
                f"Source file {source_file} does not exist. Nothing to archive."
            )

    def get_temperature(self):
        # Ta metoda powinna być zaimplementowana do pobierania aktualnej temperatury
        # Na razie zwracamy przykładową wartość
        return 20.0
