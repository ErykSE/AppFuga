import pyarrow.parquet as pq

# Odczytaj plik .parquet
table = pq.read_table(
    "C:/eryk/AppFuga/apps/backend/power_profile/detailed/2024-08-06.parquet"
)

# Konwertuj do pandas DataFrame
df = table.to_pandas()

# Wyświetl pierwsze kilka wierszy
print(df.head())
