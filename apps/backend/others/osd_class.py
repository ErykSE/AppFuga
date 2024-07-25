import json


class OSD:
    """
    Klasa definiująca aktualne warunki kontraktowe.
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
    def validate_data(cls, data):
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

        if (
            not data.get("CONTRACTED_EXPORT_POSSIBILITY", False)
            and data.get("sold_power", 0) > 0
        ):
            errors.append("Sold power > 0 but export is not possible")

        if data.get("sold_power", 0) > data.get("CONTRACTED_SALE_LIMIT", 0):
            errors.append("Sold power exceeds sale limit")

        if data.get("bought_power", 0) > data.get("CONTRACTED_PURCHASE_LIMIT", 0):
            errors.append("Bought power exceeds purchase limit")

        return errors

    @classmethod
    def load_data_from_json(cls, contract_file_path, tariffs_file_path):
        try:
            with open(contract_file_path, "r") as file:
                contract_data = json.load(file)
            with open(tariffs_file_path, "r") as file:
                tariffs_data = json.load(file)

            # Popraw literówki w danych taryf
            if "current_tarrif_buy" in tariffs_data:
                tariffs_data["current_tariff_buy"] = tariffs_data.pop(
                    "current_tarrif_buy"
                )
            if "current_tarrif_sell" in tariffs_data:
                tariffs_data["current_tariff_sell"] = tariffs_data.pop(
                    "current_tarrif_sell"
                )

            combined_data = {**contract_data, **tariffs_data}

            errors = cls.validate_data(combined_data)
            if errors:
                for error in errors:
                    print(f"Validation error: {error}")
                raise ValueError("Invalid OSD data")

            # Filtruj dane, aby pasowały do argumentów konstruktora
            init_params = cls.__init__.__code__.co_varnames[1:]  # Pomijamy 'self'
            filtered_data = {k: v for k, v in combined_data.items() if k in init_params}

            instance = cls(**filtered_data)
            print("OSD instance created successfully")
            return instance
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

    def update_tariffs(self, new_buy_price, new_sell_price):
        self.current_tariff_buy = new_buy_price
        self.current_tariff_sell = new_sell_price
        print(
            f"Zaktualizowano taryfy: kupno {self.current_tariff_buy}, sprzedaż {self.current_tariff_sell}"
        )
