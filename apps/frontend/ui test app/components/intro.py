import PyQt6.QtWidgets as qtw
import PyQt6.QtGui as qtg

from PyQt6.QtCore import Qt
import sys


class MyApp(qtw.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        # Lista przechowująca dodane urządzenia
        self.device_list = []

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

        label_pv = qtw.QLabel("PV Panel")
        btn_add_pv = qtw.QPushButton("Add PV Panel", self)
        btn_add_pv.clicked.connect(lambda: self.add_device("PV Panel"))

        label_wind_turbine = qtw.QLabel("Wind Turbine")
        btn_add_wind_turbine = qtw.QPushButton("Add Wind Turbine", self)
        btn_add_wind_turbine.clicked.connect(lambda: self.add_device("Wind Turbine"))

        ########
        # Pola do wprowadzania parametrów urządzenia
        self.device_name_edit = qtw.QLineEdit()
        self.device_quantity_edit = qtw.QLineEdit()
        self.device_power_edit = qtw.QLineEdit()

        self.device_name_edit.setPlaceholderText("Nazwa urządzenia")
        self.device_quantity_edit.setPlaceholderText("Ilość")
        self.device_power_edit.setPlaceholderText("Moc (kW)")

        ########

        left_layout.addWidget(label_add_device)
        left_layout.addWidget(label_pv)
        left_layout.addWidget(btn_add_pv)
        left_layout.addWidget(label_wind_turbine)
        left_layout.addWidget(btn_add_wind_turbine)

        left_layout.addWidget(self.device_name_edit)
        left_layout.addWidget(self.device_quantity_edit)
        left_layout.addWidget(self.device_power_edit)

        ########

        # Lista urządzeń

        self.device_list_widget = qtw.QListWidget()
        left_layout.addWidget(self.device_list_widget)

        # Prawa strona: checkboxy umowy
        right_widget = qtw.QWidget()
        right_layout = qtw.QVBoxLayout(right_widget)

        label_contract = qtw.QLabel("Umowa:")
        self.checkbox_contract1 = qtw.QCheckBox("Umowa A")
        self.checkbox_contract2 = qtw.QCheckBox("Umowa B")

        right_layout.addWidget(label_contract)
        right_layout.addWidget(self.checkbox_contract1)
        right_layout.addWidget(self.checkbox_contract2)

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
        btn_generate_json.clicked.connect(self.generate_json)
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

    def generate_json(self):
        pass

    def start_algorithm(self):
        pass


app = qtw.QApplication(sys.argv)


window = MyApp()
window.show()
sys.exit(app.exec())
