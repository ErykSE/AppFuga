import json


class OSD:
    def __init__(
        self,
        CONTRACTED_TYPE,
        CONTRACTED_DURATION,
        CONTRACTED_MARGIN,
        CONTRACTED_EXPORT_POSSIBILITY,
        CONTRACTED_SALE_LIMIT,
        CONTRACTED_PURCHASE_LIMIT,
        sold_power,
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
        self.current_tariff_buy = current_tariff_buy  # Aktualna taryfa kupna
        self.current_tariff_sell = current_tariff_sell  # Aktualna taryfa sprzedaży

    @classmethod
    def load_data_from_json(cls, contract_file_path, tariffs_file_path):
        try:
            with open(contract_file_path, "r") as file:
                contract_data = json.load(file)
            with open(tariffs_file_path, "r") as file:
                tariffs_data = json.load(file)

            print("Contract Data:", contract_data)  # Logowanie danych kontraktu
            print("Tariffs Data:", tariffs_data)  # Logowanie danych taryf

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
