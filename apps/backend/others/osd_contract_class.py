class Contract:
    def __init__(
        self,
        CONTRACTED_TYPE,
        CONTRACTED_POWER,
        CONTRACTED_DURATION,
        CONTRACTED_MARGIN,
        CONTRACTED_PRICE_PER_KWH,
        CONTRACTED_EXPORT_POSSIBILITY,
        CONTRACTED_SALE_LIMIT,
    ):
        self.CONTRACTED_TYPE = CONTRACTED_TYPE
        self.CONTRACTED_POWER = CONTRACTED_POWER
        self.CONTRACTED_DURATION = CONTRACTED_DURATION
        self.CONTRACTED_MARGIN = CONTRACTED_MARGIN
        self.CONTRACTED_PRICE_PER_KWH = CONTRACTED_PRICE_PER_KWH
        self.CONTRACTED_EXPORT_POSSIBILITY = CONTRACTED_EXPORT_POSSIBILITY
        self.CONTRACTED_SALE_LIMIT = CONTRACTED_SALE_LIMIT

    def get_contracted_type(self):
        return self.CONTRACTED_TYPE

    def get_contracted_power(self):
        return self.CONTRACTED_POWER

    def get_contracted_duration(self):
        return self.CONTRACTED_DURATION

    def get_contracted_margin(self):
        return self.CONTRACTED_MARGIN

    def get_contracted_price_per_kwh(self):
        return self.CONTRACTED_PRICE_PER_KWH

    def get_contracted_export_possibility(self):
        return self.CONTRACTED_EXPORT_POSSIBILITY

    def get_contracted_price_sale_limit(self):
        return self.CONTRACTED_SALE_LIMIT

    def update_contracted_type(self, new_type):
        self.CONTRACTED_TYPE = new_type

    def update_contracted_power(self, new_power):
        self.CONTRACTED_POWER = new_power

    def update_contracted_duration(self, new_duration):
        self.CONTRACTED_DURATION = new_duration

    def update_contracted_margin(self, new_margin):
        self.CONTRACTED_MARGIN = new_margin

    def update_contracted_price_per_kwh(self, new_price):
        self.CONTRACTED_PRICE_PER_KWH = new_price

    def update_contracted_export_possibility(self, new_export_status):
        self.CONTRACTED_EXPORT_POSSIBILITY = new_export_status

    def update_contracted_price_sale_limit(self, new_sale_limit):
        self.CONTRACTED_SALE_LIMIT = new_sale_limit
