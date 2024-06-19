import sys
import json
import mysql.connector  # Przykładowy sterownik do MySQL
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox
from PyQt6.QtCore import Qt


class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("My Application")
        layout = QVBoxLayout()

        # Przycisk do generowania pliku JSON
        self.btn_generate_json = QPushButton("Generuj plik JSON", self)
        self.btn_generate_json.clicked.connect(self.generate_json_file)
        layout.addWidget(self.btn_generate_json)

        self.setLayout(layout)

    def generate_json_file(self):
        try:
            # Konfiguracja połączenia z bazą danych MySQL
            conn = mysql.connector.connect(
                host="localhost",
                database="mydatabase",
                user="myuser",
                password="mypassword",
            )

            if conn.is_connected():
                print("Connected to MySQL database")

                # Pobierz dane z bazy danych
                cursor = conn.cursor()

                # Przykładowe zapytania SQL
                cursor.execute("SELECT * FROM devices WHERE type='PV Panel'")
                pv_panels = cursor.fetchall()

                cursor.execute("SELECT * FROM devices WHERE type='Wind Turbine'")
                wind_turbines = cursor.fetchall()

                cursor.execute("SELECT * FROM contract WHERE id=1")
                contract_data = cursor.fetchone()

                cursor.close()
                conn.close()

                # Przygotowanie danych do zapisu do pliku JSON
                data = {
                    "devices": {
                        "pv_panels": [dict(row) for row in pv_panels],
                        "wind_turbines": [dict(row) for row in wind_turbines],
                    },
                    "contract": dict(contract_data),
                }

                # Stała ścieżka do zapisu pliku JSON
                save_path = "C:/Users/Username/Desktop/initial_data.json"

                # Zapis danych do pliku JSON
                with open(save_path, "w") as json_file:
                    json.dump(data, json_file, indent=4)

                QMessageBox.information(
                    self, "Sukces", "Plik JSON został wygenerowany i zapisany."
                )

            else:
                QMessageBox.warning(
                    self, "Błąd", "Nie udało się połączyć z bazą danych."
                )

        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Wystąpił błąd: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec())
