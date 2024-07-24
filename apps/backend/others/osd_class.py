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
    def load_data_from_json(cls, contract_file_path, tariffs_file_path):
        try:
            with open(contract_file_path, "r") as file:
                contract_data = json.load(file)
            with open(tariffs_file_path, "r") as file:
                tariffs_data = json.load(file)

            # print("Contract Data:", contract_data)  # Logowanie danych kontraktu
            # print("Tariffs Data:", tariffs_data)  # Logowanie danych taryf

            return cls(
                CONTRACTED_TYPE=contract_data.get("CONTRACTED_TYPE", "default_type"),
                CONTRACTED_DURATION=contract_data.get("CONTRACTED_DURATION", 0),
                CONTRACTED_MARGIN=contract_data.get("CONTRACTED_MARGIN", 0.0),
                CONTRACTED_EXPORT_POSSIBILITY=contract_data.get(
                    "CONTRACTED_EXPORT_POSSIBILITY", False
                ),
                CONTRACTED_SALE_LIMIT=contract_data.get("CONTRACTED_SALE_LIMIT", 0),
                CONTRACTED_PURCHASE_LIMIT=contract_data.get(
                    "CONTRACTED_PURCHASE_LIMIT", 0
                ),
                sold_power=contract_data.get("sold_power", 0),
                bought_power=contract_data.get("bought_power", 0),
                current_tariff_buy=tariffs_data.get("current_tariff_buy", 0.0),
                current_tariff_sell=tariffs_data.get("current_tariff_sell", 0.0),
            )
        except FileNotFoundError as e:
            print(f"File not found: {e}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
        except KeyError as e:
            print(f"Key error: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
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
