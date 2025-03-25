import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import pytz

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_weather_data(latitude, longitude, days=7):
    base_url = "https://api.open-meteo.com/v1/forecast"

    current_time = datetime.now()
    end_date = current_time + timedelta(days=days)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,direct_radiation,diffuse_radiation,shortwave_radiation,windspeed_10m,winddirection_10m,cloudcover,uv_index",
        "daily": "sunrise,sunset,uv_index_max",
        "timezone": "auto",
        "start_date": current_time.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        hourly_df = pd.DataFrame(data["hourly"])
        hourly_df["time"] = pd.to_datetime(hourly_df["time"], utc=True)

        daily_df = pd.DataFrame(data["daily"])
        daily_df["date"] = pd.to_datetime(daily_df["time"], utc=True)
        daily_df["sunrise"] = pd.to_datetime(daily_df["sunrise"], utc=True)
        daily_df["sunset"] = pd.to_datetime(daily_df["sunset"], utc=True)

        timezone = pytz.timezone(data["timezone"])
        return hourly_df, daily_df, timezone
    else:
        logger.error(f"Błąd pobierania danych: {response.status_code}")
        logger.error(f"Odpowiedź: {response.text}")
        return None, None, None


def calculate_pv_potential(df, panel_efficiency=0.2, panel_area=1.0):
    df["pv_potential"] = df["shortwave_radiation"] * panel_efficiency * panel_area
    return df


def analyze_wind_energy(df):
    df["wind_energy"] = df["windspeed_10m"].apply(
        lambda x: max(0, min((x - 3) / 9, 1)) * 2000
    )
    return df


def calculate_insolation(df):
    df["insolation"] = df["shortwave_radiation"] * 24 / 1000
    return df


def calculate_sun_position(latitude, longitude, time):
    # Uproszczone obliczenia pozycji Słońca
    day_of_year = time.timetuple().tm_yday
    declination = 23.45 * np.sin(np.radians((360 / 365) * (day_of_year - 81)))
    hour_angle = 15 * (time.hour - 12)

    elevation = np.arcsin(
        np.sin(np.radians(latitude)) * np.sin(np.radians(declination))
        + np.cos(np.radians(latitude))
        * np.cos(np.radians(declination))
        * np.cos(np.radians(hour_angle))
    )

    azimuth = np.arccos(
        (
            np.sin(np.radians(declination))
            - np.sin(np.radians(latitude)) * np.sin(elevation)
        )
        / (np.cos(np.radians(latitude)) * np.cos(elevation))
    )

    return np.degrees(elevation), np.degrees(azimuth)


def log_current_data(df, timezone, latitude, longitude):
    current_time = datetime.now(timezone)
    current_time_utc = current_time.astimezone(pytz.UTC)
    current_data = df[df["time"] <= current_time_utc].iloc[-1]

    elevation, azimuth = calculate_sun_position(latitude, longitude, current_time)

    logger.info("DANE RZECZYWISTE (AKTUALNE):")
    logger.info(f"Czas lokalny: {current_time}")
    logger.info(f"Temperatura: {current_data['temperature_2m']:.1f}°C")
    logger.info(
        f"Promieniowanie bezpośrednie: {current_data['direct_radiation']:.2f} W/m²"
    )
    logger.info(
        f"Promieniowanie rozproszone: {current_data['diffuse_radiation']:.2f} W/m²"
    )
    logger.info(
        f"Promieniowanie krótkofalowe: {current_data['shortwave_radiation']:.2f} W/m²"
    )
    logger.info(f"Nasłonecznienie: {current_data['insolation']:.2f} kWh/m²/dzień")
    logger.info(f"Indeks UV: {current_data['uv_index']:.1f}")
    logger.info(f"Zachmurzenie: {current_data['cloudcover']:.0f}%")
    logger.info(f"Potencjał PV: {current_data['pv_potential']:.2f} W")
    logger.info(f"Energia wiatrowa: {current_data['wind_energy']:.2f} W")
    logger.info(f"Pozycja Słońca - Elewacja: {elevation:.2f}°, Azymut: {azimuth:.2f}°")


def log_forecast_data(hourly_df, daily_df, timezone):
    logger.info("\nPROGNOZA:")
    current_time_utc = datetime.now(timezone).astimezone(pytz.UTC)
    for _, row in hourly_df[hourly_df["time"] > current_time_utc].iterrows():
        local_time = row["time"].astimezone(timezone)
        logger.info(
            f"Czas: {local_time}, PV potencjał: {row['pv_potential']:.2f} W, Energia wiatrowa: {row['wind_energy']:.2f} W"
        )

    logger.info("\nDANE DZIENNE:")
    for _, row in daily_df.iterrows():
        sunrise = row["sunrise"].astimezone(timezone)
        sunset = row["sunset"].astimezone(timezone)
        logger.info(
            f"Data: {row['date'].astimezone(timezone).date()}, Wschód słońca: {sunrise.time()}, Zachód słońca: {sunset.time()}, Max UV: {row['uv_index_max']:.1f}"
        )


def analyze_weather_data(hourly_df, daily_df, timezone, latitude, longitude):
    if hourly_df is not None and daily_df is not None:
        hourly_df = calculate_pv_potential(hourly_df)
        hourly_df = analyze_wind_energy(hourly_df)
        hourly_df = calculate_insolation(hourly_df)

        log_current_data(hourly_df, timezone, latitude, longitude)
        log_forecast_data(hourly_df, daily_df, timezone)

        logger.info("\nPODSUMOWANIE DANYCH:")
        logger.info(
            f"Zakres dat: od {hourly_df['time'].min().astimezone(timezone)} do {hourly_df['time'].max().astimezone(timezone)}"
        )
        logger.info(
            f"Średnie dzienne promieniowanie bezpośrednie: {hourly_df['direct_radiation'].mean():.2f} W/m²"
        )
        logger.info(
            f"Średnie dzienne promieniowanie rozproszone: {hourly_df['diffuse_radiation'].mean():.2f} W/m²"
        )
        logger.info(
            f"Średnie dzienne promieniowanie krótkofalowe: {hourly_df['shortwave_radiation'].mean():.2f} W/m²"
        )
        logger.info(
            f"Średnie dzienne nasłonecznienie: {hourly_df['insolation'].mean():.2f} kWh/m²/dzień"
        )
        logger.info(f"Średni dzienny indeks UV: {hourly_df['uv_index'].mean():.1f}")
        logger.info(
            f"Średnie dzienne zachmurzenie: {hourly_df['cloudcover'].mean():.0f}%"
        )
        logger.info(
            f"Średni dzienny potencjał fotowoltaiczny: {hourly_df['pv_potential'].mean()*24:.2f} Wh/m²"
        )
        logger.info(
            f"Średnia dzienna produkcja energii wiatrowej: {hourly_df['wind_energy'].mean()*24:.2f} Wh"
        )
    else:
        logger.error("Brak danych do analizy.")


# Użycie
latitude = 52.23
longitude = 21.01

hourly_data, daily_data, timezone = get_weather_data(latitude, longitude)
analyze_weather_data(hourly_data, daily_data, timezone, latitude, longitude)
