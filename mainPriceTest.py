import pandas as pd
from entsoe import EntsoePandasClient
from datetime import datetime, timedelta

# Klucz API - zastąp swoim kluczem
api_key = "0b3d2450-fe30-4038-8d86-b891cfc31307"

# Inicjalizacja klienta
client = EntsoePandasClient(api_key=api_key)

# Parametry
country_code = "PL"  # Kod kraju (Polska)
end = pd.Timestamp(datetime.now().strftime("%Y%m%d%H%M"), tz="Europe/Brussels")
start_actual = end - timedelta(days=1)  # Dane rzeczywiste z ostatnich 24 godzin
start_forecast = end  # Prognoza na następne 24 godziny
end_forecast = end + timedelta(days=1)


def display_data(data, title):
    print(f"\n{title}:")
    print(data)
    print("\n" + "-" * 50)


# 1. Ceny energii
try:
    # Rzeczywiste ceny
    actual_prices = client.query_day_ahead_prices(
        country_code, start=start_actual, end=end
    )
    display_data(actual_prices, "Rzeczywiste ceny energii na rynku day-ahead")

    # Prognozowane ceny (jeśli dostępne)
    forecast_prices = client.query_day_ahead_prices(
        country_code, start=start_forecast, end=end_forecast
    )
    display_data(forecast_prices, "Prognozowane ceny energii na rynku day-ahead")
except Exception as e:
    print(f"Błąd podczas pobierania cen energii: {e}")

# 2. Produkcja energii
try:
    # Rzeczywista produkcja
    actual_generation = client.query_generation(
        country_code, start=start_actual, end=end
    )
    display_data(actual_generation, "Rzeczywista produkcja energii według typu")

    # Prognoza produkcji wiatrowej i słonecznej
    wind_solar_forecast = client.query_wind_and_solar_forecast(
        country_code, start=start_forecast, end=end_forecast
    )
    display_data(
        wind_solar_forecast, "Prognoza produkcji energii wiatrowej i słonecznej"
    )
except Exception as e:
    print(f"Błąd podczas pobierania danych o produkcji: {e}")

# 3. Zużycie energii
try:
    # Rzeczywiste zużycie
    actual_load = client.query_load(country_code, start=start_actual, end=end)
    display_data(actual_load, "Rzeczywiste zużycie energii")

    # Prognoza zużycia
    load_forecast = client.query_load_forecast(
        country_code, start=start_forecast, end=end_forecast
    )
    display_data(load_forecast, "Prognoza zużycia energii")
except Exception as e:
    print(f"Błąd podczas pobierania danych o zużyciu: {e}")

# 4. Porównanie rzeczywistych i prognozowanych danych
try:
    print("\nPorównanie rzeczywistych i prognozowanych danych dla ostatniej godziny:")
    last_hour = end.floor("H")

    print(f"Cena energii:")
    print(f"  Rzeczywista: {actual_prices.loc[last_hour]} EUR/MWh")
    print(f"  Prognozowana: {forecast_prices.loc[last_hour]} EUR/MWh")

    print(f"\nZużycie energii:")
    print(f"  Rzeczywiste: {actual_load.loc[last_hour]} MW")
    print(f"  Prognozowane: {load_forecast.loc[last_hour]} MW")

    print(f"\nProdukcja energii wiatrowej i słonecznej:")
    actual_wind_solar = actual_generation.loc[
        last_hour, ["Wind Onshore", "Wind Offshore", "Solar"]
    ].sum()
    forecast_wind_solar = wind_solar_forecast.loc[
        last_hour, ["Wind Onshore", "Wind Offshore", "Solar"]
    ].sum()
    print(f"  Rzeczywista: {actual_wind_solar} MW")
    print(f"  Prognozowana: {forecast_wind_solar} MW")
except Exception as e:
    print(f"Błąd podczas porównywania danych: {e}")

print("\nPobieranie danych zakończone.")
