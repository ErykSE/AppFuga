import PyQt6.QtWidgets as qtw
import PyQt6.QtGui as qtg
import json

from PyQt6.QtCore import Qt
import sys

# from apps.frontend.components.test.test import testfunkcji


class MyApp(qtw.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        # Lista przechowująca dodane urządzenia
        self.device_list = []
        self.contract_data_list = []

    def initUI(self):
        self.setWindowTitle("Test UI")
        self.resize(800, 500)

        layout = qtw.QVBoxLayout()

        tabs = qtw.QTabWidget()

        # First tab

        tab1 = qtw.QWidget()
        main_tab1_layout = qtw.QVBoxLayout()  # Główny layout dla zakładki 1
        splitter = qtw.QSplitter(Qt.Orientation.Horizontal)

        #####tab1_layout = qtw.QHBoxLayout()

        # Etykiety i przyciski dla urządzeń

        # Lewa strona: dodawanie urządzeń do listy
        left_widget = qtw.QWidget()
        left_layout = qtw.QVBoxLayout(left_widget)

        label_add_device = qtw.QLabel("Dodaj urządzenie:")

        # Lista rozwijana do wyboru typu urządzenia
        self.device_type_combo = qtw.QComboBox()
        self.device_type_combo.addItems(
            ["BESS", "Fuel Cell", "Fuel Turbine", "PV Panel", "Wind Turbine"]
        )
        self.device_type_combo.currentIndexChanged.connect(self.update_param_fields)

        left_layout.addWidget(label_add_device)
        left_layout.addWidget(self.device_type_combo)

        # Layout do dynamicznego dodawania pól parametrów
        self.param_layout = qtw.QFormLayout()
        left_layout.addLayout(self.param_layout)

        self.update_param_fields()  # Wywołanie na początku, aby ustawić pola dla domyślnego wyboru

        # Przycisk dodania urządzenia do listy
        self.btn_add_device = qtw.QPushButton("Dodaj urządzenie do listy", self)
        self.btn_add_device.clicked.connect(self.add_device)
        left_layout.addWidget(self.btn_add_device)

        # Lista urządzeń
        self.device_list_widget = qtw.QListWidget()
        left_layout.addWidget(self.device_list_widget)

        # Prawa strona: elementy dotyczące umowy
        right_widget = qtw.QWidget()
        right_layout = qtw.QVBoxLayout(right_widget)

        label_contract = qtw.QLabel("Contract details:")
        right_layout.addWidget(label_contract)

        # Elementy związane z umową
        self.export_checkbox = qtw.QCheckBox("Czy możliwy jest eksport energii")
        self.contracted_limit_edit = qtw.QLineEdit()

        self.contracted_limit_edit.setPlaceholderText("Zakontraktowany limit sprzedaży")
        self.contracted_limit_edit.setEnabled(False)

        self.export_checkbox.stateChanged.connect(self.toggle_contracted_limit)

        self.contract_type_label = qtw.QLabel("Rodzaj umowy:")
        self.instantaneous_consumption_checkbox = qtw.QCheckBox("Zużycie chwilowe")
        self.cumulative_consumption_checkbox = qtw.QCheckBox("Zużycie sumaryczne")

        # Grupa przycisków, aby wymusić wybranie tylko jednego z checkboxów
        self.contract_type_group = qtw.QButtonGroup()
        self.contract_type_group.addButton(self.instantaneous_consumption_checkbox)
        self.contract_type_group.addButton(self.cumulative_consumption_checkbox)
        self.contract_type_group.setExclusive(True)

        self.max_consumption_edit = qtw.QLineEdit()
        self.max_consumption_edit.setPlaceholderText(
            "Zakontraktowane maksymalne zużycie"
        )

        self.contract_length_edit = qtw.QLineEdit()
        self.contract_length_edit.setPlaceholderText("Zakontraktowana długość umowy")

        self.margin_edit = qtw.QLineEdit()
        self.margin_edit.setPlaceholderText("Zakontraktowany margines")

        self.price_edit = qtw.QLineEdit()
        self.price_edit.setPlaceholderText("Zakontraktowana cena")

        right_layout.addWidget(self.export_checkbox)
        right_layout.addWidget(self.contracted_limit_edit)
        right_layout.addWidget(self.contract_type_label)
        right_layout.addWidget(self.instantaneous_consumption_checkbox)
        right_layout.addWidget(self.cumulative_consumption_checkbox)
        right_layout.addWidget(self.max_consumption_edit)
        right_layout.addWidget(self.contract_length_edit)
        right_layout.addWidget(self.margin_edit)
        right_layout.addWidget(self.price_edit)

        # Dodanie przycisku dane do listy

        btn_add_contract_data = qtw.QPushButton("Add contract data", self)
        btn_add_contract_data.clicked.connect(self.add_contract_data)
        right_layout.addWidget(btn_add_contract_data)

        # Lista

        self.contract_data_list_widget = qtw.QListWidget()
        right_layout.addWidget(self.contract_data_list_widget)

        # Dodanie lewego i prawego widgetu do splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        # Dodanie splittera do głównego layoutu zakładki 1
        main_tab1_layout.addWidget(splitter)

        # Przycisk zapisu do bazy danych

        btn_save = qtw.QPushButton("Save data to database", self)
        btn_save.clicked.connect(self.save_data)

        # Układ na zakładce

        spacer = qtw.QSpacerItem(
            20, 40, qtw.QSizePolicy.Policy.Minimum, qtw.QSizePolicy.Policy.Expanding
        )

        main_tab1_layout.addItem(spacer)
        main_tab1_layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignCenter)

        tab1.setLayout(main_tab1_layout)

        # Second tab

        tab2 = qtw.QWidget()
        tab2_layout = qtw.QVBoxLayout()

        self.table_view = qtw.QTableView()

        # Settings

        self.table_view.horizontalHeader().setSectionResizeMode(
            qtw.QHeaderView.ResizeMode.Stretch
        )
        self.table_view.horizontalHeader().setStyleSheet(
            "QHeaderView::section {border: 1px solid #6c6c6c;}"
        )

        self.table_view.verticalHeader().setStyleSheet(
            "QHeaderView::section {border: 1px solid #6c6c6c;}"
        )

        tab2_layout.addWidget(self.table_view)
        btn_load = qtw.QPushButton("Load data from databse", self)
        btn_load.clicked.connect(self.load_data)
        tab2_layout.addWidget(btn_load)
        tab2.setLayout(tab2_layout)

        # Third tab

        tab3 = qtw.QWidget()
        tab3_layout = qtw.QVBoxLayout()

        btn_generate_json = qtw.QPushButton("Generate JSON", self)
        btn_generate_json.clicked.connect(self.generate_json_file)

        tab3_layout.addWidget(btn_generate_json)
        tab3.setLayout(tab3_layout)

        # Fourth tab

        tab4 = qtw.QWidget()
        tab4_layout = qtw.QVBoxLayout()
        btn_start_algorithm = qtw.QPushButton("Start", self)
        btn_start_algorithm.clicked.connect(self.start_algorithm)
        tab4_layout.addWidget(btn_start_algorithm)
        tab4.setLayout(tab4_layout)

        ########################

        tabs.addTab(tab1, "Save data")
        tabs.addTab(tab2, "Load data")
        tabs.addTab(tab3, "Generate JSON")
        tabs.addTab(tab4, "Main Application")
        layout.addWidget(tabs)
        self.setLayout(layout)

    def toggle_contracted_limit(self, state):
        if state == 2:
            self.contracted_limit_edit.setEnabled(True)
        else:
            self.contracted_limit_edit.setEnabled(False)

    def update_param_fields(self):
        # Czyszczenie obecnych pól
        while self.param_layout.rowCount() > 0:
            self.param_layout.removeRow(0)

        device_type = self.device_type_combo.currentText()

        if device_type == "PV Panel":
            self.device_name_edit = qtw.QLineEdit()
            self.device_data1_edit = qtw.QLineEdit()
            self.device_power_edit = qtw.QLineEdit()

            self.device_name_edit.setPlaceholderText("Device name")
            self.device_data1_edit.setPlaceholderText("data1")
            self.device_power_edit.setPlaceholderText("Power (kW)")

            self.param_layout.addRow("Device name:", self.device_name_edit)
            self.param_layout.addRow("data1:", self.device_data1_edit)
            self.param_layout.addRow("Power (kW):", self.device_power_edit)

        elif device_type == "Wind Turbine":
            self.device_name_edit = qtw.QLineEdit()
            self.device_data1_edit = qtw.QLineEdit()
            self.device_power_edit = qtw.QLineEdit()

            self.device_name_edit.setPlaceholderText("Device name")
            self.device_data1_edit.setPlaceholderText("data1")
            self.device_power_edit.setPlaceholderText("Power (kW)")

            self.param_layout.addRow("Device name:", self.device_name_edit)
            self.param_layout.addRow("data1:", self.device_data1_edit)
            self.param_layout.addRow("Power (kW):", self.device_power_edit)

        elif device_type == "BESS":
            self.device_name_edit = qtw.QLineEdit()
            self.device_data1_edit = qtw.QLineEdit()

            self.device_name_edit.setPlaceholderText("Device name")
            self.device_data1_edit.setPlaceholderText("data1")

            self.param_layout.addRow("Device name:", self.device_name_edit)
            self.param_layout.addRow("data1:", self.device_data1_edit)

        elif device_type == "Fuel Turbine":
            self.device_name_edit = qtw.QLineEdit()
            self.device_data1_edit = qtw.QLineEdit()

            self.device_name_edit.setPlaceholderText("Device name")
            self.device_data1_edit.setPlaceholderText("data1")

            self.param_layout.addRow("Device name:", self.device_name_edit)
            self.param_layout.addRow("data1:", self.device_data1_edit)

        elif device_type == "Fuel Cell":
            self.device_name_edit = qtw.QLineEdit()
            self.device_data1_edit = qtw.QLineEdit()

            self.device_name_edit.setPlaceholderText("Device name")
            self.device_data1_edit.setPlaceholderText("data1")

            self.param_layout.addRow("Device name:", self.device_name_edit)
            self.param_layout.addRow("data1:", self.device_data1_edit)

    def add_device(self):
        # Dodanie urządzenia do listy na podstawie wybranego typu i parametrów
        device_type = self.device_type_combo.currentText()
        device_params = {}

        for i in range(self.param_layout.rowCount()):
            label = (
                self.param_layout.itemAt(i, qtw.QFormLayout.ItemRole.LabelRole)
                .widget()
                .text()
            )
            field = (
                self.param_layout.itemAt(i, qtw.QFormLayout.ItemRole.FieldRole)
                .widget()
                .text()
            )
            device_params[label] = field

        if any(not value for value in device_params.values()):
            qtw.QMessageBox.warning(
                self, "Uwaga", "Proszę wprowadzić wszystkie parametry urządzenia."
            )
            return

        device_info = f"{device_type}: {', '.join(f'{key} {value}' for key, value in device_params.items())}"
        self.device_list.append(device_info)
        item = qtw.QListWidgetItem(device_info)
        self.device_list_widget.addItem(item)

        # Czyszczenie pól po dodaniu urządzenia
        for i in range(self.param_layout.rowCount()):
            self.param_layout.itemAt(
                i, qtw.QFormLayout.ItemRole.FieldRole
            ).widget().clear()

    def add_contract_data(self):

        self.contract_data_list_widget.clear()
        self.contract_data_list = []

        contract_data = {
            "Export energy": (
                "Possible" if self.export_checkbox.isChecked() else "Impossible"
            ),
            "Contracted limit": (
                self.contracted_limit_edit.text()
                if self.export_checkbox.isChecked()
                else ""
            ),
            "Contract type": (
                "Instananeous consumption"
                if self.instantaneous_consumption_checkbox.isChecked()
                else "Cumulative consumption"
            ),
            "Max consumption": self.max_consumption_edit.text(),
            "Contract length": self.contract_length_edit.text(),
            "Margin": self.margin_edit.text(),
            "Price": self.price_edit.text(),
        }

        self.contract_data_list.append(contract_data)

        # Wyświetlenie danych w QListWidget
        contract_data_str = (
            f"Export energy: {contract_data['Export energy']}, "
            f"Contracted limit: {contract_data['Contracted limit']}, "
            f"Contract type: {contract_data['Contract type']}, "
            f"Max consumption: {contract_data['Max consumption']}, "
            f"Contract length: {contract_data['Contract length']}, "
            f"Margin: {contract_data['Margin']}, "
            f"Price: {contract_data['Price']}"
        )

        self.contract_data_list_widget.addItem(contract_data_str)

    def save_data(self):
        pass

    def load_data(self):
        data = [
            {"id": 1, "data1": "value1", "data2": "value2", "data3": "value3"},
            {"id": 2, "data1": "value4", "data2": "value5", "data3": "value6"},
        ]

        model = qtg.QStandardItemModel()

        model.setHorizontalHeaderLabels(["ID", "Data 1", "Data 2", "Data 3"])

        for item in data:
            row = [
                qtg.QStandardItem(str(item["id"])),
                qtg.QStandardItem(item["data1"]),
                qtg.QStandardItem(item["data2"]),
                qtg.QStandardItem(item["data3"]),
            ]
            model.appendRow(row)

        self.table_view.setModel(model)

    def generate_json_file(self):
        # Przykładowe dane do zapisu w pliku JSON (na potrzeby testów)
        data = {
            "devices": [
                {"type": "PV Panel", "name": "Panel 1", "quantity": 2, "power_kW": 5.5},
                {
                    "type": "Wind Turbine",
                    "name": "Turbine 1",
                    "quantity": 1,
                    "power_kW": 10.0,
                },
            ],
            "contract": {
                "export_energy": True,
                "contracted_limit": 1000,
                "contract_type": "Instantaneous consumption",
                "max_consumption": 500,
                "contract_length": "1 year",
                "margin": 10,
                "price": 0.15,
            },
        }

        # Stała ścieżka do zapisu pliku JSON
        save_path = "C:/eryk/AppFuga/apps/backend/initial_data.json"

        # Zapis danych do pliku JSON
        try:
            with open(save_path, "w") as json_file:
                json.dump(data, json_file, indent=4)
            qtw.QMessageBox.information(
                self, "Sukces", "Plik JSON został wygenerowany i zapisany."
            )
        except Exception as e:
            qtw.QMessageBox.warning(
                self, "Błąd", f"Wystąpił błąd podczas zapisu pliku: {str(e)}"
            )

    def start_algorithm(self):
        pass


app = qtw.QApplication(sys.argv)


window = MyApp()
window.show()
sys.exit(app.exec())
