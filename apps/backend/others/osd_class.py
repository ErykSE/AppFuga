import json
from typing import Any, Dict, List


class OSD:
    """
    Klasa definiująca aktualne warunki kontraktowe dla Operatora Systemu Dystrybucyjnego (OSD).

    Klasa ta przechowuje informacje o kontrakcie, limitach sprzedaży i zakupu energii,
    aktualnych taryfach oraz bieżącym stanie sprzedaży i zakupu energii.
    
    ZAKTUALIZOWANA: Dodano wsparcie dla loggerów i dodatkowe pola billing.

    Attributes:
        CONTRACTED_TYPE (str): Typ kontraktu.
        CONTRACTED_DURATION (int): Czas trwania kontraktu w miesiącach.
        CONTRACTED_MARGIN (float): Uzgodniona marża kontraktowa.
        CONTRACTED_EXPORT_POSSIBILITY (bool): Możliwość eksportu energii.
        CONTRACTED_SALE_LIMIT (float): Limit sprzedaży energii w kWh.
        CONTRACTED_PURCHASE_LIMIT (float): Limit zakupu energii w kWh.
        sold_power (float): Całkowita ilość sprzedanej energii w kWh.
        bought_power (float): Całkowita ilość zakupionej energii w kWh.
        current_tariff_buy (float): Aktualna taryfa zakupu energii.
        current_tariff_sell (float): Aktualna taryfa sprzedaży energii.
        current_grid_export (float): Aktualny setpoint eksportu do sieci w kW.
        current_grid_import (float): Aktualny setpoint importu z sieci w kW.
    """

    def __init__(
        self,
        CONTRACTED_TYPE,
        CONTRACTED_DURATION,
        CONTRACTED_MARGIN,
        CONTRACTED_EXPORT_POSSIBILITY,
        CONTRACTED_SALE_LIMIT,
        CONTRACTED_PURCHASE_LIMIT,
        sold_power=0,
        bought_power=0,
        current_tariff_buy=0,
        current_tariff_sell=0,
        contracted_billing_cycle="monthly",
        contracted_billing_period_start="",
        contracted_billing_period_end="",
        decision_mode="AUTO",
        info_logger=None,
        error_logger=None,
    ):
        self.CONTRACTED_TYPE = CONTRACTED_TYPE
        self.CONTRACTED_DURATION = CONTRACTED_DURATION
        self.CONTRACTED_MARGIN = CONTRACTED_MARGIN
        self.CONTRACTED_EXPORT_POSSIBILITY = CONTRACTED_EXPORT_POSSIBILITY
        self.CONTRACTED_SALE_LIMIT = CONTRACTED_SALE_LIMIT
        self.CONTRACTED_PURCHASE_LIMIT = CONTRACTED_PURCHASE_LIMIT

        # NOWE: Dodatkowe pola billing (opcjonalne)
        self.contracted_billing_cycle = contracted_billing_cycle
        self.contracted_billing_period_start = contracted_billing_period_start
        self.contracted_billing_period_end = contracted_billing_period_end

        # Dane dynamiczne
        self.sold_power = sold_power
        self.bought_power = bought_power
        self.current_tariff_buy = current_tariff_buy
        self.current_tariff_sell = current_tariff_sell

        # === GRID OPERATIONS - SETPOINTY (polecenia dla SCADA) ===
        self.setpoint_grid_export = 0.0  # ✅ NOWE: Polecenie eksportu
        self.setpoint_grid_import = 0.0  # ✅ NOWE: Polecenie importu
        
        # === GRID OPERATIONS - ACTUAL (stan rzeczywisty z SCADA) ===
        self.actual_grid_export = 0.0    # ✅ NOWE: Rzeczywisty eksport
        self.actual_grid_import = 0.0    # ✅ NOWE: Rzeczywisty import
        
        # === BACKWARD COMPATIBILITY ===
        self.current_grid_export = 0.0   # ⚠️  DEPRECATED
        self.current_grid_import = 0.0   # ⚠️  DEPRECATED

        self.decision_mode = decision_mode
    
        # Walidacja
        valid_modes = ["AUTO", "CHARGE_PRIORITY", "SELL_PRIORITY"]
        if decision_mode not in valid_modes:
            if error_logger:
                error_logger.warning(
                    f"Invalid decision_mode '{decision_mode}', using AUTO. "
                    f"Valid: {valid_modes}"
                )
            self.decision_mode = "AUTO"

        self.name = "OSD"

        # NOWE: Loggery
        self.info_logger = info_logger
        self.error_logger = error_logger

    @classmethod
    def validate_data(cls, data: Dict[str, Any]) -> List[str]:
        """
        Waliduje dane wejściowe dla klasy OSD.

        Args:
            data (Dict[str, Any]): Słownik zawierający dane do walidacji.

        Returns:
            List[str]: Lista błędów walidacji. Pusta lista oznacza brak błędów.
        """
        errors = []
        required_fields = [
            "CONTRACTED_TYPE",
            "CONTRACTED_DURATION",
            "CONTRACTED_MARGIN",
            "CONTRACTED_EXPORT_POSSIBILITY",
            "CONTRACTED_SALE_LIMIT",
            "CONTRACTED_PURCHASE_LIMIT",
            "sold_power",
            "bought_power",
            "current_tariff_buy",
            "current_tariff_sell",
        ]

        for field in required_fields:
            if field not in data:
                errors.append(f"Missing field: {field}")

        if "CONTRACTED_TYPE" in data and not isinstance(data["CONTRACTED_TYPE"], str):
            errors.append("CONTRACTED_TYPE must be a string")

        if "CONTRACTED_DURATION" in data and not isinstance(
            data["CONTRACTED_DURATION"], int
        ):
            errors.append("CONTRACTED_DURATION must be an integer")

        if "CONTRACTED_MARGIN" in data and not isinstance(
            data["CONTRACTED_MARGIN"], (int, float)
        ):
            errors.append("CONTRACTED_MARGIN must be a number")

        if "CONTRACTED_EXPORT_POSSIBILITY" in data and not isinstance(
            data["CONTRACTED_EXPORT_POSSIBILITY"], bool
        ):
            errors.append("CONTRACTED_EXPORT_POSSIBILITY must be a boolean")

        for field in [
            "CONTRACTED_SALE_LIMIT",
            "CONTRACTED_PURCHASE_LIMIT",
            "sold_power",
            "bought_power",
            "current_tariff_buy",
            "current_tariff_sell",
        ]:
            if field in data and not isinstance(data[field], (int, float)):
                errors.append(f"{field} must be a number")

        if not data.get("CONTRACTED_EXPORT_POSSIBILITY", False):
            if data.get("CONTRACTED_SALE_LIMIT", 0) != 0:
                errors.append(
                    "CONTRACTED_SALE_LIMIT must be 0 when CONTRACTED_EXPORT_POSSIBILITY is False"
                )
            if data.get("sold_power", 0) != 0:
                errors.append(
                    "sold_power must be 0 when CONTRACTED_EXPORT_POSSIBILITY is False"
                )
        else:
            if data.get("CONTRACTED_SALE_LIMIT", 0) < 0:
                errors.append("CONTRACTED_SALE_LIMIT cannot be negative")
            if data.get("sold_power", 0) < 0:
                errors.append("sold_power cannot be negative")

        return errors

    @classmethod
    def load_data_from_json(cls, contract_file_path: str, info_logger=None, error_logger=None) -> "OSD":
        """
        Wczytuje dane z pliku JSON i tworzy instancję klasy OSD.
        
        ZAKTUALIZOWANA: 
        - Obsługa billing cycle
        - Obsługa grid operations (current_grid_export/import)
        - Lepsze logowanie
        - Bezpieczne ładowanie z wartościami domyślnymi

        Args:
            contract_file_path (str): Ścieżka do pliku JSON z danymi kontraktu.
            info_logger: Logger do informacji (opcjonalny)
            error_logger: Logger do błędów (opcjonalny)

        Returns:
            OSD: Instancja klasy OSD lub None w przypadku błędu.
        """
        try:
            log_msg = f"Attempting to load OSD data from: {contract_file_path}"
            if info_logger:
                info_logger.info(log_msg)
            else:
                print(log_msg)

            # Wczytaj plik JSON
            with open(contract_file_path, "r", encoding='utf-8') as file:
                data = json.load(file)

            if info_logger:
                info_logger.info("Raw contract data loaded:")
                info_logger.info(json.dumps(data, indent=2))
            else:
                print("Raw contract data loaded:")
                print(json.dumps(data, indent=2))

            # Walidacja danych
            errors = cls.validate_data(data)
            if errors:
                for error in errors:
                    if error_logger:
                        error_logger.error(f"Validation error: {error}")
                    else:
                        print(f"Validation error: {error}")
                return None

            # Tworzenie instancji OSD z bezpiecznymi wartościami domyślnymi
            instance = cls(
                # === DANE KONTRAKTOWE (wymagane) ===
                CONTRACTED_TYPE=data.get("CONTRACTED_TYPE"),
                CONTRACTED_DURATION=data.get("CONTRACTED_DURATION"),
                CONTRACTED_MARGIN=data.get("CONTRACTED_MARGIN"),
                CONTRACTED_EXPORT_POSSIBILITY=data.get("CONTRACTED_EXPORT_POSSIBILITY"),
                CONTRACTED_SALE_LIMIT=data.get("CONTRACTED_SALE_LIMIT"),
                CONTRACTED_PURCHASE_LIMIT=data.get("CONTRACTED_PURCHASE_LIMIT"),
                
                # === DANE BIEŻĄCE (z wartościami domyślnymi) ===
                sold_power=data.get("sold_power", 0),
                bought_power=data.get("bought_power", 0),
                current_tariff_buy=data.get("current_tariff_buy", 0),
                current_tariff_sell=data.get("current_tariff_sell", 0),
                
                # === BILLING CYCLE (opcjonalne, z wartościami domyślnymi) ===
                contracted_billing_cycle=data.get("CONTRACTED_BILLING_CYCLE", 
                                                data.get("contracted_billing_cycle", "monthly")),
                contracted_billing_period_start=data.get("contracted_billing_period_start", ""),
                contracted_billing_period_end=data.get("contracted_billing_period_end", ""),
                
                decision_mode=data.get("decision_mode", "AUTO"),
                
                # === LOGGERY ===
                info_logger=info_logger,
                error_logger=error_logger
            )
            
            # ✅ NOWE: Jeśli JSON zawiera grid operations (setpointy i actual)
            if "setpoint_grid_export" in data:
                instance.setpoint_grid_export = data.get("setpoint_grid_export", 0.0)
            if "setpoint_grid_import" in data:
                instance.setpoint_grid_import = data.get("setpoint_grid_import", 0.0)
            if "actual_grid_export" in data:
                instance.actual_grid_export = data.get("actual_grid_export", 0.0)
            if "actual_grid_import" in data:
                instance.actual_grid_import = data.get("actual_grid_import", 0.0)
            
            # Backward compatibility - jeśli JSON ma stare pola
            if "current_grid_export" in data:
                instance.current_grid_export = data.get("current_grid_export", 0.0)
                # Użyj jako actual jeśli nie ma actual_*
                if "actual_grid_export" not in data:
                    instance.actual_grid_export = instance.current_grid_export
            if "current_grid_import" in data:
                instance.current_grid_import = data.get("current_grid_import", 0.0)
                # Użyj jako actual jeśli nie ma actual_*
                if "actual_grid_import" not in data:
                    instance.actual_grid_import = instance.current_grid_import
            
            # Logowanie sukcesu
            if info_logger:
                info_logger.info("OSD instance created successfully")
                info_logger.info("Loaded contract data:")
                info_logger.info(f"  CONTRACTED_TYPE: {instance.CONTRACTED_TYPE}")
                info_logger.info(f"  CONTRACTED_DURATION: {instance.CONTRACTED_DURATION}")
                info_logger.info(f"  CONTRACTED_MARGIN: {instance.CONTRACTED_MARGIN}")
                info_logger.info(f"  CONTRACTED_EXPORT_POSSIBILITY: {instance.CONTRACTED_EXPORT_POSSIBILITY}")
                info_logger.info(f"  CONTRACTED_SALE_LIMIT: {instance.CONTRACTED_SALE_LIMIT}")
                info_logger.info(f"  CONTRACTED_PURCHASE_LIMIT: {instance.CONTRACTED_PURCHASE_LIMIT}")
                info_logger.info(f"  contracted_billing_cycle: {instance.contracted_billing_cycle}")
                info_logger.info(f"  sold_power: {instance.sold_power}")
                info_logger.info(f"  bought_power: {instance.bought_power}")
                info_logger.info(f"  current_tariff_buy: {instance.current_tariff_buy}")
                info_logger.info(f"  current_tariff_sell: {instance.current_tariff_sell}")
                info_logger.info(f"  current_grid_export: {instance.current_grid_export}")
                info_logger.info(f"  current_grid_import: {instance.current_grid_import}")
                info_logger.info(f"  decision_mode: {instance.decision_mode}")
            else:
                print("OSD instance created successfully")
                print("Loaded contract data:")
                print(f"  CONTRACTED_TYPE: {instance.CONTRACTED_TYPE}")
                print(f"  CONTRACTED_DURATION: {instance.CONTRACTED_DURATION}")
                print(f"  sold_power: {instance.sold_power}")
                print(f"  bought_power: {instance.bought_power}")
            
            return instance
            
        except FileNotFoundError:
            error_msg = f"Contract file not found: {contract_file_path}"
            if error_logger:
                error_logger.error(error_msg)
            else:
                print(error_msg)
            return None
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in contract file: {contract_file_path}"
            if error_logger:
                error_logger.error(error_msg)
                error_logger.error(f"JSON decode error: {str(e)}")
            else:
                print(error_msg)
                print(f"JSON decode error: {str(e)}")
            return None
            
        except KeyError as e:
            error_msg = f"Missing required field in contract data: {str(e)}"
            if error_logger:
                error_logger.error(error_msg)
                error_logger.exception("Full traceback:")
            else:
                print(error_msg)
            return None
            
        except Exception as e:
            error_msg = f"An error occurred while loading OSD data: {e}"
            if error_logger:
                error_logger.error(error_msg)
                error_logger.exception(f"Exception details: {type(e).__name__}, {str(e)}")
            else:
                print(error_msg)
                print(f"Exception details: {type(e).__name__}, {str(e)}")
            return None

    def get_contracted_export_possibility(self):
        """Zwraca czy eksport energii jest dozwolony kontraktem."""
        return self.CONTRACTED_EXPORT_POSSIBILITY

    def get_sale_limit(self):
        """Zwraca limit sprzedaży energii z kontraktu."""
        return self.CONTRACTED_SALE_LIMIT

    def get_sold_power(self):
        """Zwraca całkowitą ilość sprzedanej energii."""
        return self.sold_power

    def get_bought_power(self):
        """Zwraca całkowitą ilość zakupionej energii."""
        return self.bought_power

    def get_purchase_limit(self):
        """Zwraca limit zakupu energii z kontraktu."""
        return self.CONTRACTED_PURCHASE_LIMIT

    def buy_power(self, amount):
        """Kupuje energię z sieci."""
        remaining_capacity = self.get_remaining_purchase_capacity()
        amount_to_buy = min(amount, remaining_capacity)
        
        if amount_to_buy > 0:
            self.bought_power += amount_to_buy
            
            # ✅ POPRAWKA: Ustaw SETPOINT (polecenie dla SCADA)
            self.setpoint_grid_import = amount_to_buy
            # ✅ Reset eksportu
            self.setpoint_grid_export = 0.0
            
            # ✅ POPRAWKA: Symulacja nie jest potrzebna - używamy setpoint
            
            # Backward compatibility
            self.current_grid_import = amount_to_buy
            self.current_grid_export = 0.0
            
            if self.info_logger:
                self.info_logger.info(
                    f"Buying {amount_to_buy:.2f} kW from grid (setpoint). "
                    f"Total bought: {self.bought_power:.2f} kWh"
                )
            
            return amount_to_buy
        
        return 0.0

    def sell_power(self, amount):
        """Sprzedaje energię do sieci."""
        if not self.CONTRACTED_EXPORT_POSSIBILITY:
            return 0.0
        
        remaining_capacity = self.get_remaining_sale_capacity()
        amount_to_sell = min(amount, remaining_capacity)
        
        if amount_to_sell > 0:
            self.sold_power += amount_to_sell
            
            # ✅ POPRAWKA: Ustaw SETPOINT (polecenie dla SCADA)
            self.setpoint_grid_export = amount_to_sell
            # ✅ Reset importu
            self.setpoint_grid_import = 0.0
            
            # ✅ POPRAWKA: Symulacja nie jest potrzebna - używamy setpoint
            
            # Backward compatibility
            self.current_grid_export = amount_to_sell
            self.current_grid_import = 0.0
            
            if self.info_logger:
                self.info_logger.info(
                    f"Selling {amount_to_sell:.2f} kW to grid (setpoint). "
                    f"Total sold: {self.sold_power:.2f} kWh"
                )
            
            return amount_to_sell
        
        return 0.0

    def reset_current_grid_values(self):
        """Resetuje setpointy grid na początku iteracji."""
        self.setpoint_grid_export = 0.0  # ✅ NOWE
        self.setpoint_grid_import = 0.0  # ✅ NOWE
        
        # Backward compatibility
        self.current_grid_export = 0.0
        self.current_grid_import = 0.0
        
        if self.info_logger:
            self.info_logger.debug("Reset grid setpoints to 0.0")

    def get_current_grid_export(self):
        """Zwraca aktualny setpoint eksportu do sieci w kW"""
        return self.current_grid_export

    def get_current_grid_import(self):
        """Zwraca aktualny setpoint importu z sieci w kW"""
        return self.current_grid_import

    def get_current_buy_price(self):
        """Zwraca aktualną cenę zakupu energii."""
        return self.current_tariff_buy

    def get_current_sell_price(self):
        """Zwraca aktualną cenę sprzedaży energii."""
        return self.current_tariff_sell

    def get_contracted_sale_limit(self):
        """Zwraca kontraktowy limit sprzedaży."""
        return self.CONTRACTED_SALE_LIMIT

    def get_remaining_sale_capacity(self):
        """Zwraca pozostałą pojemność sprzedaży."""
        return max(0, self.CONTRACTED_SALE_LIMIT - self.sold_power)

    def get_remaining_purchase_capacity(self):
        """Zwraca pozostałą pojemność zakupu."""
        return max(0, self.CONTRACTED_PURCHASE_LIMIT - self.bought_power)

    def can_sell_energy(self):
        """Sprawdza czy możliwa jest sprzedaż energii."""
        return (
            self.CONTRACTED_EXPORT_POSSIBILITY
            and self.get_remaining_sale_capacity() > 0
        )

    def can_buy_energy(self):
        """Sprawdza czy możliwy jest zakup energii."""
        return self.get_remaining_purchase_capacity() > 0

    def can_sell_more(self, amount):
        """Sprawdza czy możliwa jest sprzedaż określonej ilości energii."""
        return self.can_sell_energy() and self.get_remaining_sale_capacity() >= amount

    def can_buy_more(self, amount):
        """Sprawdza czy możliwy jest zakup określonej ilości energii."""
        return (
            self.can_buy_energy() and self.get_remaining_purchase_capacity() >= amount
        )

    def update_tariffs(self, new_buy_price: float, new_sell_price: float) -> None:
        """
        Aktualizuje taryfy kupna i sprzedaży energii.
        
        ZAKTUALIZOWANA: Użyto loggerów zamiast print.

        Args:
            new_buy_price (float): Nowa cena zakupu energii.
            new_sell_price (float): Nowa cena sprzedaży energii.
        """
        self.current_tariff_buy = new_buy_price
        self.current_tariff_sell = new_sell_price
        
        if self.info_logger:
            self.info_logger.info(
                f"Updated tariffs: buy {self.current_tariff_buy:.3f} $/kWh, "
                f"sell {self.current_tariff_sell:.3f} $/kWh"
            )
        else:
            print(
                f"Zaktualizowano taryfy: kupno {self.current_tariff_buy}, "
                f"sprzedaż {self.current_tariff_sell}"
            )

    def to_dict(self):
        """
        Konwertuje obiekt OSD do słownika dla API.
        
        ⚠️  Ta metoda zwraca TYLKO dane DO WYSŁANIA do API/SCADA.
        
        WYSYŁANE:
        - Billing (akumulatory): sold_power, bought_power
        - Setpointy (polecenia): setpoint_grid_export, setpoint_grid_import
        
        NIE WYSYŁANE (READ-ONLY):
        - Kontraktowe (stałe): CONTRACTED_*
        - Taryfy (zewnętrzne): current_tariff_*
        - Actual (stan): actual_grid_*
        - Decision mode (konfiguracja): decision_mode
        
        Returns:
            dict: Słownik zawierający TYLKO pola do wysłania
        """
        return {
            # ✅ BILLING - Stan sprzedaży/zakupu (zapisujemy postęp)
            "sold_power": self.sold_power,
            "bought_power": self.bought_power,
            
            # ✅ SETPOINTY - Polecenia dla SCADA
            "setpoint_grid_export": self.setpoint_grid_export,
            "setpoint_grid_import": self.setpoint_grid_import,
            
            # ⚠️  BACKWARD COMPATIBILITY (do usunięcia po migracji)
            "current_grid_export": self.current_grid_export,
            "current_grid_import": self.current_grid_import,
        }

    def __str__(self):
        """Reprezentacja tekstowa obiektu OSD."""
        return (
            f"OSD(Type: {self.CONTRACTED_TYPE}, "
            f"Export: {self.current_grid_export:.2f} kW, "
            f"Import: {self.current_grid_import:.2f} kW)"
        )

    def __repr__(self):
        """Reprezentacja deweloperska obiektu OSD."""
        return (
            f"OSD(type={self.CONTRACTED_TYPE}, "
            f"export={self.current_grid_export:.2f} kW, "
            f"import={self.current_grid_import:.2f} kW, "
            f"sold={self.sold_power:.2f}/{self.CONTRACTED_SALE_LIMIT:.2f} kWh, "
            f"bought={self.bought_power:.2f}/{self.CONTRACTED_PURCHASE_LIMIT:.2f} kWh)"
        )