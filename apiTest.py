import requests
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import urllib3

# Wyłącz ostrzeżenia SSL dla lokalnego developmentu
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ScadaApiClient:
    def __init__(
        self, base_url: str = "https://localhost:7106/api/scada", data_dir: str = "data"
    ):
        """
        Inicjalizacja klienta API SCADA.

        Args:
            base_url: Bazowy URL API
            data_dir: Katalog do przechowywania plików JSON
        """
        self.base_url = base_url.rstrip("/")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Konfiguracja sesji HTTP
        self.session = requests.Session()
        # Wyłącz weryfikację SSL dla localhost
        self.session.verify = False

        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

        # Konfiguracja logowania
        self.setup_logging()

        # Test połączenia przy inicjalizacji
        self.test_connection()

    def setup_logging(self):
        """Konfiguracja systemu logowania"""
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            # Log do pliku
            fh = logging.FileHandler(self.data_dir / "scada_api.log")
            fh.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(fh)

            # Log do konsoli
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            self.logger.addHandler(ch)

    def test_connection(self):
        """Test połączenia z API"""
        try:
            self.logger.info(f"Testing connection to {self.base_url}")
            response = self.session.get(f"{self.base_url}/system-state", timeout=5)
            response.raise_for_status()
            self.logger.info("Successfully connected to API")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to API: {str(e)}")
            raise

    def get_system_state(self, save_to_file: bool = True) -> Dict[str, Any]:
        """
        Pobiera aktualny stan systemu.
        """
        try:
            self.logger.info("Requesting system state...")
            response = self.session.get(f"{self.base_url}/system-state")
            response.raise_for_status()

            data = response.json()
            self.logger.info("Successfully retrieved system state")

            if save_to_file:
                self._save_data(data, "system_state")

            return data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting system state: {str(e)}")
            raise

    def update_system_state(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aktualizuje stan systemu.
        """
        try:
            self.logger.info("Sending system state update...")
            response = self.session.post(
                f"{self.base_url}/update-system-state", json=updates
            )
            response.raise_for_status()

            result = response.json()
            self.logger.info("Successfully updated system state")
            return result

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error updating system state: {str(e)}")
            raise

    def _save_data(self, data: Dict[str, Any], prefix: str):
        """Zapisuje dane do pliku JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.data_dir / f"{prefix}_{timestamp}.json"

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Saved data to {filepath}")

        except IOError as e:
            self.logger.error(f"Error saving data to file: {str(e)}")
            raise

    def update_from_file(self, filepath: str) -> Dict[str, Any]:
        """
        Aktualizuje stan systemu na podstawie pliku JSON.

        Args:
            filepath: Ścieżka do pliku JSON z aktualizacjami

        Returns:
            Dict z odpowiedzią serwera
        """
        try:
            self.logger.info(f"Reading updates from file: {filepath}")

            # Sprawdź czy plik istnieje
            if not Path(filepath).exists():
                raise FileNotFoundError(f"File not found: {filepath}")

            # Wczytaj dane z pliku
            with open(filepath, "r") as f:
                updates = json.load(f)

            self.logger.info(f"Successfully read updates from {filepath}")

            # Wykonaj aktualizację
            return self.update_system_state(updates)

        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON file: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error processing update file: {str(e)}")
            raise

    def run():
        print("Starting SCADA API Client...")
        try:
            # Stwórz klienta
            client = ScadaApiClient()

            # 1. Pobierz stan systemu
            print("\nPobieranie stanu systemu...")
            system_state = client.get_system_state()
            print("Otrzymane dane:")
            print(json.dumps(system_state, indent=2))

            # 2. Przykład aktualizacji bezpośredniej
            print("\nWysyłanie bezpośredniej aktualizacji...")
            updates = {
                "fuel_turbines": [
                    {
                        "name": "FuelTurbine1",
                        "actual_output": 35.5,
                        "switch_status": True,
                    }
                ]
            }

            update_result = client.update_system_state(updates)
            print("Wynik bezpośredniej aktualizacji:")
            print(json.dumps(update_result, indent=2))

            # 3. Przykład aktualizacji z pliku
            print("\nWysyłanie aktualizacji z pliku...")

            update_file = "updates.json"
            # with open(update_file, "w") as f:
            #  json.dump(update_file, f, indent=2)
            # print(f"Created example update file: {update_file}")

            # Wykonaj aktualizację z pliku
            file_update_result = client.update_from_file(update_file)
            print("Wynik aktualizacji z pliku:")
            print(json.dumps(file_update_result, indent=2))

        except Exception as e:
            print(f"\nWystąpił błąd: {str(e)}")
            print("\nSprawdź czy:")
            print("1. API jest uruchomione w Visual Studio")
            print("2. URL jest poprawny (https://localhost:7106/api/scada)")
            print("3. Swagger UI działa w przeglądarce")


ScadaApiClient.run()
