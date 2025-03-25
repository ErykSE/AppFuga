import requests
from datetime import datetime, timedelta
import pandas as pd
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)  # Wyłącz ostrzeżenia SSL


# base_url="https://10.234.191.56:7194"):


class EnergyApiClient:
    def __init__(self, base_url="https://localhost:7194"):  # Zaktualizowany URL
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False  # Wyłącz weryfikację SSL dla localhost

    def get_five_minute_data(self, timestamp):
        """Pobiera dane 5-minutowe dla konkretnej godziny"""
        url = f"{self.base_url}/api/EnergyData/five-minute/{timestamp.strftime('%Y-%m-%dT%H:%M:%S')}"
        print(f"Requesting URL: {url}")  # Debugging
        response = self.session.get(url)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    def get_hourly_data(self, date):
        """Pobiera dane godzinowe dla konkretnego dnia"""
        url = f"{self.base_url}/api/EnergyData/hourly/{date.strftime('%Y-%m-%d')}"
        print(f"Requesting URL: {url}")  # Debugging
        response = self.session.get(url)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    def get_historical_data(self, start_date, end_date):
        """Pobiera dane historyczne dla zakresu dat"""
        url = f"{self.base_url}/api/EnergyData/historical"
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
        }
        print(f"Requesting URL: {url} with params: {params}")  # Debugging
        response = self.session.get(url, params=params)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None


def test_api():
    client = EnergyApiClient()

    # Test 1: Dane 5-minutowe
    print("\nTesting 5-minute data...")
    timestamp = datetime(2024, 10, 1, 18, 0)  # 14:00
    data_5min = client.get_five_minute_data(timestamp)
    if data_5min is not None:
        print(f"Retrieved {len(data_5min)} 5-minute records")
        print(data_5min)

    # Test 2: Dane godzinowe
    print("\nTesting hourly data...")
    date = datetime(2023, 8, 1)
    data_hourly = client.get_hourly_data(date)
    if data_hourly is not None:
        print(f"Retrieved {len(data_hourly)} hourly records")
        print(data_hourly)

    """

    # Test 3: Dane historyczne
    print("\nTesting historical data...")
    start_date = datetime(2023, 8, 1)
    end_date = datetime(2023, 8, 7)
    data_historical = client.get_historical_data(start_date, end_date)
    if data_historical is not None:
        print(f"Retrieved {len(data_historical)} historical records")
        print(data_historical.head())

    """


test_api()
