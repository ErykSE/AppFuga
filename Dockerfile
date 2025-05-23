FROM python:3.9

# Utwórz strukturę katalogów jak w środowisku lokalnym
RUN mkdir -p /C:/eryk/AppFuga/apps/backend

# Ustaw katalog roboczy
WORKDIR /app

# Kopiuj requirements.txt i zainstaluj zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiuj cały projekt do /app
COPY . .

# Skopiuj pliki konfiguracyjne do specyficznej lokalizacji Windows
COPY apps/backend/initial_data.json /C:/eryk/AppFuga/apps/backend/
COPY apps/backend/contract_data.json /C:/eryk/AppFuga/apps/backend/
COPY apps/backend/operation_mode.json /C:/eryk/AppFuga/apps/backend/

# Utwórz katalogi docelowe i skopiuj pliki do lokalizacji, której szuka aplikacja
RUN mkdir -p C:/eryk/AppFuga/apps/backend/ && \
    cp /C:/eryk/AppFuga/apps/backend/*.json C:/eryk/AppFuga/apps/backend/

# Uruchom aplikację
CMD ["python", "main_algorithm.py"]