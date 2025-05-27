Plan Testów - System Zarządzania Mikrosiecią Energetyczną
1. Wprowadzenie
1.1 Cel dokumentu
Dokument opisuje strategię testowania systemu zarządzania mikrosiecią energetyczną, definiuje zakres testów, podejście, wymagane zasoby oraz harmonogram.
1.2 Opis systemu
System składa się z:

Aplikacji Python (serce systemu)
SCADA API (komunikacja z urządzeniami)
DATA API (dostęp do danych historycznych)
Warstwy cache (Redis)
Konteneryzacji (Docker)

2. Strategia testowania
2.1 Poziomy testów

Testy jednostkowe: Weryfikacja poprawności działania poszczególnych komponentów
Testy integracyjne: Sprawdzenie komunikacji między komponentami
Testy systemowe: Testowanie całego systemu
Testy wydajnościowe: Sprawdzenie zachowania systemu pod obciążeniem

2.2 Typy testów

Testy funkcjonalne
Testy niefunkcjonalne (wydajność, niezawodność)
Testy regresji
Testy API

3. Zakres testów
3.1 Aplikacja Python

Komunikacja z SCADA
Pobieranie danych zewnętrznych (pogoda, ceny energii)
Logika biznesowa i algorytmy decyzyjne
Tworzenie i aktualizacja profili mocy
Zapisywanie danych do plików parquet

3.2 DATA API

Endpointy GET /api/EnergyData/five-minute/{timestamp}
Endpointy GET /api/EnergyData/hourly/{date}
Endpointy GET /api/EnergyData/historical?startDate&endDate
Mechanizm cache (Redis)

3.3 Integracja

Przepływ danych z SCADA do aplikacji Python
Przepływ danych z aplikacji Python do plików parquet
Przepływ danych z plików parquet do DATA API

3.4 Docker

Konfiguracja kontenerów
Komunikacja między kontenerami
Wolumeny i persystencja danych

4. Środowiska testowe
4.1 Środowisko deweloperskie

Lokalne maszyny deweloperskie
Mockowane zewnętrzne API

4.2 Środowisko testowe

Dedykowane środowisko w Docker
Mock serwer SCADA
Testowa instancja Redis

4.3 Środowisko produkcyjne (testy akceptacyjne)

Konfiguracja zbliżona do docelowej
Rzeczywiste lub symulowane urządzenia

5. Zasoby i narzędzia
5.1 Zespół testowy

Deweloperzy (testy jednostkowe)
Tester (testy integracyjne i systemowe)

5.2 Narzędzia

pytest: Framework do testów jednostkowych i integracyjnych
pytest-mock: Do mockowania zależności
pytest-cov: Do analizy pokrycia kodu testami
Postman/Newman: Do testowania API
locust: Do testów wydajnościowych
GitHub Issues: Do śledzenia błędów i zadań testowych

5.3 Dane testowe

Symulowane dane z urządzeń
Historyczne profile mocy
Przykładowe dane pogodowe i cenowe

6. Harmonogram testów
FazaZakresPlanowany terminStatusFaza 1Testy jednostkowe aplikacji PythonTBDNie rozpoczętoFaza 2Testy integracyjne SCADA-PythonTBDNie rozpoczętoFaza 3Testy DATA API i cacheTBDNie rozpoczętoFaza 4Testy systemowe w DockerTBDNie rozpoczętoFaza 5Testy wydajnościoweTBDNie rozpoczęto
7. Kryteria rozpoczęcia i zakończenia testów
7.1 Kryteria rozpoczęcia

Zakończony rozwój danego komponentu
Dostępne środowisko testowe
Przygotowane dane testowe

7.2 Kryteria zakończenia

90% pokrycia kodu testami jednostkowymi
Wszystkie testy integracyjne zakończone sukcesem
Brak błędów krytycznych
System wytrzymuje obciążenie X zapytań/s

8. Raportowanie
8.1 Raportowanie defektów

Szczegółowy opis problemu
Kroki reprodukcji
Oczekiwane vs rzeczywiste rezultaty
Priorytet i dotkliwość

8.2 Raportowanie postępu

Cotygodniowe aktualizacje matrycy pokrycia
Raporty z wykonanych testów

9. Zarządzanie ryzykiem
RyzykoPrawdopodobieństwoWpływStrategia mitygacjiProblemy z integracją SCADAŚrednieWysokiWczesne testy integracyjne, mockowanieWydajność przy dużej ilości danychWysokieŚredniTesty wydajnościowe z dużymi zestawami danychProblemy z konteneryzacjąNiskieŚredniDedykowane środowisko testowe Docker
10. Załączniki

Szablon raportu z testów
Szablon zgłoszenia defektu
Matryca pokrycia testami (osobny dokument)