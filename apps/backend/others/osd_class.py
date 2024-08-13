import json
from typing import Any, Dict, List


class OSD:
    """
    Klasa definiująca aktualne warunki kontraktowe dla Operatora Systemu Dystrybucyjnego (OSD).

    Klasa ta przechowuje informacje o kontrakcie, limitach sprzedaży i zakupu energii,
    aktualnych taryfach oraz bieżącym stanie sprzedaży i zakupu energii.

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
    """

    def __init__(
        self,
        CONTRACTED_TYPE,
        CONTRACTED_DURATION,
        CONTRACTED_MARGIN,
        CONTRACTED_EXPORT_POSSIBILITY,
        CONTRACTED_SALE_LIMIT,
        CONTRACTED_PURCHASE_LIMIT,
        sold_power,
        bought_power,
        current_tariff_buy,
        current_tariff_sell,
    ):
        self.CONTRACTED_TYPE = CONTRACTED_TYPE
        self.CONTRACTED_DURATION = CONTRACTED_DURATION
        self.CONTRACTED_MARGIN = CONTRACTED_MARGIN
        self.CONTRACTED_EXPORT_POSSIBILITY = CONTRACTED_EXPORT_POSSIBILITY
        self.CONTRACTED_SALE_LIMIT = CONTRACTED_SALE_LIMIT
        self.CONTRACTED_PURCHASE_LIMIT = CONTRACTED_PURCHASE_LIMIT

        # Dane dynamiczne
        self.sold_power = sold_power  # Całkowita moc sprzedana
        self.bought_power = bought_power  # Całkowita moc sprzedana
        self.current_tariff_buy = current_tariff_buy  # Aktualna taryfa kupna
        self.current_tariff_sell = current_tariff_sell  # Aktualna taryfa sprzedaży

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
    def load_data_from_json(cls, contract_file_path: str) -> "OSD":
        """
        Wczytuje dane z pliku JSON i tworzy instancję klasy OSD.

        Args:
            contract_file_path (str): Ścieżka do pliku JSON z danymi kontraktu i taryf.

        Returns:
            OSD: Instancja klasy OSD lub None w przypadku błędu.

        Raises:
            ValueError: Jeśli dane są nieprawidłowe.
        """
        try:
            print(f"Attempting to load OSD data from: {contract_file_path}")
            with open(contract_file_path, "r") as file:
                data = json.load(file)

            print("Raw contract data loaded:")
            print(json.dumps(data, indent=2))

            errors = cls.validate_data(data)
            if errors:
                for error in errors:
                    print(f"Validation error: {error}")
                return None

            init_params = cls.__init__.__code__.co_varnames[1:]
            filtered_data = {k: v for k, v in data.items() if k in init_params}

            instance = cls(**filtered_data)
            print("OSD instance created successfully")
            print("Loaded contract data:")
            for key, value in filtered_data.items():
                print(f"  {key}: {value}")
            return instance
        except FileNotFoundError:
            print(f"Contract file not found: {contract_file_path}")
        except json.JSONDecodeError:
            print(f"Invalid JSON in contract file: {contract_file_path}")
        except Exception as e:
            print(f"An error occurred while loading OSD data: {e}")
            print(f"Exception details: {type(e).__name__}, {str(e)}")
        return None

    def get_contracted_export_possibility(self):
        return self.CONTRACTED_EXPORT_POSSIBILITY

    def get_sale_limit(self):
        return self.CONTRACTED_SALE_LIMIT

    def get_sold_power(self):
        return self.sold_power

    def get_bought_power(self):
        return self.bought_power

    def get_purchase_limit(self):
        return self.CONTRACTED_PURCHASE_LIMIT

    def buy_power(self, amount):
        amount_to_buy = min(amount, self.get_remaining_purchase_capacity())
        self.bought_power += amount_to_buy
        return amount_to_buy

    def get_current_buy_price(self):
        return self.current_tariff_buy

    def get_current_sell_price(self):
        return self.current_tariff_sell

    def get_contracted_sale_limit(self):
        return self.CONTRACTED_SALE_LIMIT

    def sell_power(self, amount):
        amount_to_sell = min(amount, self.get_remaining_sale_capacity())
        self.sold_power += amount_to_sell
        return amount_to_sell

    def get_remaining_sale_capacity(self):
        return max(0, self.CONTRACTED_SALE_LIMIT - self.sold_power)

    def get_remaining_purchase_capacity(self):
        return max(0, self.CONTRACTED_PURCHASE_LIMIT - self.bought_power)

    def can_sell_energy(self):
        return (
            self.CONTRACTED_EXPORT_POSSIBILITY
            and self.get_remaining_sale_capacity() > 0
        )

    def can_buy_energy(self):
        return self.get_remaining_purchase_capacity() > 0

    def can_sell_more(self, amount):
        return self.can_sell_energy() and self.get_remaining_sale_capacity() >= amount

    def can_buy_more(self, amount):
        return (
            self.can_buy_energy() and self.get_remaining_purchase_capacity() >= amount
        )

    def update_tariffs(self, new_buy_price: float, new_sell_price: float) -> None:
        """
        Aktualizuje taryfy kupna i sprzedaży energii.

        Args:
            new_buy_price (float): Nowa cena zakupu energii.
            new_sell_price (float): Nowa cena sprzedaży energii.
        """
        self.current_tariff_buy = new_buy_price
        self.current_tariff_sell = new_sell_price
        print(
            f"Zaktualizowano taryfy: kupno {self.current_tariff_buy}, sprzedaż {self.current_tariff_sell}"
        )
