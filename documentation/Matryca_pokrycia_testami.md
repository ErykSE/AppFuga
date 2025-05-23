# Matryca Pokrycia Testami

## Aplikacja Python

| ID | Funkcjonalność | Priorytet | Test Jednostkowy | Test Integracyjny | Test Wydajnościowy | Status | Uwagi |
|----|----------------|-----------|------------------|-------------------|-------------------|--------|-------|
| PY-001 | Połączenie z SCADA API | Wysoki | ❌ test_scada_connection | ❌ test_scada_integration | - | Nie rozpoczęto | |
| PY-002 | Odczyt tagów SCADA | Wysoki | ❌ test_tag_reading | ❌ test_tag_monitoring | - | Nie rozpoczęto | |
| PY-003 | Zapis tagów SCADA | Średni | ❌ test_tag_writing | ❌ test_tag_control | - | Nie rozpoczęto | |
| PY-004 | Połączenie z API pogodowym | Średni | ❌ test_weather_api_connection | - | - | Nie rozpoczęto | |
| PY-005 | Pobieranie danych pogodowych | Średni | ❌ test_weather_data_fetching | - | - | Nie rozpoczęto | |
| PY-006 | Połączenie z API cen energii | Średni | ❌ test_energy_price_api_connection | - | - | Nie rozpoczęto | |
| PY-007 | Pobieranie danych o cenach | Średni | ❌ test_energy_price_fetching | - | - | Nie rozpoczęto | |
| PY-008 | Tworzenie profilu mocy (5min) | Wysoki | ❌ test_power_profile_creation | ❌ test_profile_accuracy | ❌ test_profile_performance | Nie rozpoczęto | |
| PY-009 | Agregacja do danych godzinowych | Wysoki | ❌ test_hourly_aggregation | ❌ test_aggregation_flow | - | Nie rozpoczęto | |
| PY-010 | Agregacja do danych historycznych | Średni | ❌ test_historical_aggregation | ❌ test_metrics_calculation | - | Nie rozpoczęto | |
| PY-011 | Algorytm decyzyjny | Krytyczny | ❌ test_decision_algorithm | ❌ test_algorithm_integration | ❌ test_algorithm_performance | Nie rozpoczęto | |
| PY-012 | Obsługa wyjątków i błędów | Wysoki | ❌ test_error_handling | ❌ test_system_recovery | - | Nie rozpoczęto | |

## DATA API

| ID | Funkcjonalność | Priorytet | Test Jednostkowy | Test Integracyjny | Test Wydajnościowy | Status | Uwagi |
|----|----------------|-----------|------------------|-------------------|-------------------|--------|-------|
| API-001 | Endpoint five-minute | Wysoki | ❌ test_five_minute_endpoint | ❌ test_five_minute_integration | ❌ test_five_minute_load | Nie rozpoczęto | |
| API-002 | Endpoint hourly | Wysoki | ❌ test_hourly_endpoint | ❌ test_hourly_integration | ❌ test_hourly_load | Nie rozpoczęto | |
| API-003 | Endpoint historical | Wysoki | ❌ test_historical_endpoint | ❌ test_historical_integration | ❌ test_historical_load | Nie rozpoczęto | |
| API-004 | Parametry zapytań | Średni | ❌ test_query_parameters | - | - | Nie rozpoczęto | |
| API-005 | Obsługa błędów API | Wysoki | ❌ test_api_error_handling | - | - | Nie rozpoczęto | |
| API-006 | Format odpowiedzi JSON | Średni | ❌ test_json_response_format | - | - | Nie rozpoczęto | |

## Redis Cache

| ID | Funkcjonalność | Priorytet | Test Jednostkowy | Test Integracyjny | Test Wydajnościowy | Status | Uwagi |
|----|----------------|-----------|------------------|-------------------|-------------------|--------|-------|
| CACHE-001 | Zapisywanie do cache | Wysoki | ❌ test_redis_write | ❌ test_cache_write_integration | - | Nie rozpoczęto | |
| CACHE-002 | Odczyt z cache | Wysoki | ❌ test_redis_read | ❌ test_cache_read_integration | ❌ test_cache_read_performance | Nie rozpoczęto | |
| CACHE-003 | TTL dla różnych danych | Średni | ❌ test_ttl_implementation | ❌ test_ttl_expiration | - | Nie rozpoczęto | |
| CACHE-004 | Odporność na awarię Redis | Wysoki | ❌ test_redis_failure_handling | ❌ test_system_without_cache | - | Nie rozpoczęto | |

## Docker i Środowisko

| ID | Funkcjonalność | Priorytet | Test Jednostkowy | Test Integracyjny | Test Wydajnościowy | Status | Uwagi |
|----|----------------|-----------|------------------|-------------------|-------------------|--------|-------|
| DOCKER-001 | Budowanie obrazów | Wysoki | - | ❌ test_docker_build | - | Nie rozpoczęto | |
| DOCKER-002 | Komunikacja między kontenerami | Wysoki | - | ❌ test_container_communication | - | Nie rozpoczęto | |
| DOCKER-003 | Persystencja danych (wolumeny) | Wysoki | - | ❌ test_data_persistence | - | Nie rozpoczęto | |
| DOCKER-004 | Restart kontenerów | Średni | - | ❌ test_container_restart | - | Nie rozpoczęto | |
| DOCKER-005 | Wydajność w środowisku Docker | Średni | - | - | ❌ test_docker_performance | Nie rozpoczęto | |

## Legenda statusów:

- ✅ Zakończono pomyślnie
- ⚠️ Zakończono z uwagami
- ❌ Nie rozpoczęto / Nie zaliczono
- 🔄 W trakcie