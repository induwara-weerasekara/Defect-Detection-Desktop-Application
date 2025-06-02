
from PyQt5.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
import datetime
import csv
from detection import DetectionThread
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import traceback
from database import Database  # Import the Database class
from ArduinoCommunication import ArduinoCommunication


class GraphWindow(QDialog):
    def __init__(self, detection_data=None):
        super().__init__()
        try:
            self.setWindowTitle("Defect Detection Statistics")
            self.setGeometry(100, 100, 1000, 800)

            self.figure = Figure()
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)

            layout = QVBoxLayout()
            layout.addWidget(self.canvas)
            self.setLayout(layout)

            self.detection_data = detection_data if detection_data else {
                "Intact": [],
                "Damaged-Deformed": [],
                "Damaged-Open": []
            }
            self.time_steps = []

            self.plot_data()
        except Exception as e:
            print(f"Error initializing GraphWindow: {e}")
            traceback.print_exc()

    def plot_data(self):
        try:
            self.ax.clear()

            max_length = max(
                len(self.time_steps),
                len(self.detection_data["Intact"]),
                len(self.detection_data["Damaged-Deformed"]),
                len(self.detection_data["Damaged-Open"])
            )

            if len(self.time_steps) < max_length:
                self.time_steps = list(range(1, max_length + 1))

            has_data = False

            if self.detection_data["Intact"]:
                self.ax.plot(
                    self.time_steps[:len(self.detection_data["Intact"])],
                    self.detection_data["Intact"],
                    label="Intact (Good Boxes)",
                    marker="o",
                    color="green",
                    linewidth=2
                )
                has_data = True

            if self.detection_data["Damaged-Deformed"]:
                self.ax.plot(
                    self.time_steps[:len(self.detection_data["Damaged-Deformed"])],
                    self.detection_data["Damaged-Deformed"],
                    label="Damaged-Deformed (Bad Boxes)",
                    marker="s",
                    color="red",
                    linewidth=2
                )
                has_data = True

            if self.detection_data["Damaged-Open"]:
                self.ax.plot(
                    self.time_steps[:len(self.detection_data["Damaged-Open"])],
                    self.detection_data["Damaged-Open"],
                    label="Damaged-Open (Bad Boxes)",
                    marker="^",
                    color="blue",
                    linewidth=2
                )
                has_data = True

            self.ax.set_xlabel("Time Step", fontsize=12)
            self.ax.set_ylabel("Count", fontsize=12)
            self.ax.set_title("Defect Detection Over Time", fontsize=14, fontweight="bold")

            plt.xticks(rotation=45, ha="right")
            self.ax.grid(True, linestyle="--", alpha=0.6)

            if has_data:
                self.ax.legend(
                    loc="upper center",
                    bbox_to_anchor=(0.5, 1.15),
                    ncol=3,
                    fontsize=10
                )

            self.figure.tight_layout()
            self.canvas.draw()
        except Exception as e:
            print(f"Error plotting data: {e}")
            traceback.print_exc()

    def update_data(self, new_data):
        try:
            for key in self.detection_data:
                if key in new_data:
                    self.detection_data[key].append(new_data[key])
                else:
                    self.detection_data[key].append(0)

            self.time_steps.append(len(self.time_steps) + 1)
            self.plot_data()
        except Exception as e:
            print(f"Error updating data: {e}")
            traceback.print_exc()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Defect Detection Application")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize the database
        self.db = Database()

        # Initialize UI components
        self.init_ui()

        # Initialize Arduino communication
        self.arduino = ArduinoCommunication(port='COM3')  # Change 'COM3' to your Arduino's port
        if not self.arduino.connect():
            self.append_log("Failed to connect to Arduino.")

        self.graph_window = None
        self.detection_data = {"Intact": [], "Damaged-Deformed": [], "Damaged-Open": []}


        self.full_screen_mode = False
        self.showMaximized()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.video_label = QLabel()
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.video_label, stretch=8)

        self.stats_layout = QVBoxLayout()

        self.counter_layout = QHBoxLayout()
        self.total_label = QLabel("Total Count: 0")
        self.intact_label = QLabel("Intact Count: 0")
        self.deformed_label = QLabel("Damaged-Deformed Count: 0")
        self.open_label = QLabel("Damaged-Open Count: 0")

        for label in [self.total_label, self.intact_label, self.deformed_label, self.open_label]:
            label.setStyleSheet("font-size: 16px; padding: 5px;")
            self.counter_layout.addWidget(label)
        self.stats_layout.addLayout(self.counter_layout)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #f1f1f1; font-size: 14px;")
        self.log_area.setFixedHeight(100)
        self.stats_layout.addWidget(self.log_area)

        self.main_layout.addLayout(self.stats_layout, stretch=2)

        self.button_layout = QHBoxLayout()
        self.create_button("Start Webcam", "#4CAF50", self.start_webcam_detection)
        self.create_button("Select File", "#008CBA", self.start_file_detection)
        self.create_button("Pause", "#FFC107", self.pause_detection)
        self.create_button("Resume", "#4CAF50", self.resume_detection)
        self.create_button("Stop", "#f44336", self.stop_detection)
        self.create_button("Export Report", "#673AB7", self.export_report)
        self.create_button("Open Graph", "#FF5722", self.open_graph_window)
        self.main_layout.addLayout(self.button_layout, stretch=1)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Timestamp", "Status", "Details"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.setFixedHeight(120)
        self.main_layout.addWidget(self.table_widget, stretch=2)

        self.detection_thread = None
        self.total_count = 0
        self.intact_count = 0
        self.deformed_count = 0
        self.open_count = 0

        self.consecutive_defective_count = 0

    def create_button(self, text, color, action):
        button = QPushButton(text)
        button.setStyleSheet(f"background-color: {color}; color: white; font-size: 14px; padding: 8px;")
        button.clicked.connect(action)
        self.button_layout.addWidget(button)

    def update_display(self, pixmap: QPixmap):
        if pixmap:
            scaled_pixmap = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.video_label.setPixmap(scaled_pixmap)

    def update_counters(self, result: str):
        if result not in ["Intact", "Damaged-Deformed", "Damaged-Open"]:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result == "Intact":
            self.intact_count += 1
            details = "Box is intact and properly sealed."
            sorting_msg = "✅ Intact box detected. Sorting to the intact side."
            self.consecutive_defective_count = 0  # Reset only for intact objects
            # Send signal to Arduino for green bulb
            self.arduino.send_defect_status("Intact")
        elif result == "Damaged-Deformed":
            self.deformed_count += 1
            details = "Box is deformed or punctured."
            sorting_msg = "❌ Damaged-Deformed box detected. Sorting to the reject side."
            self.consecutive_defective_count += 1
            # Send signal to Arduino for red bulb
            self.arduino.send_defect_status("Defective")
        else:
            self.open_count += 1
            details = "Box is improperly sealed or open."
            sorting_msg = "❌ Damaged-Open box detected. Sorting to the reject side."
            self.consecutive_defective_count += 1
            # Send signal to Arduino for red bulb
            self.arduino.send_defect_status("Defective")

        self.total_count += 1

        print(f"Consecutive Defective Count: {self.consecutive_defective_count}")

        self.total_label.setText(f"Total Count: {self.total_count}")
        self.intact_label.setText(f"Intact Count: {self.intact_count}")
        self.deformed_label.setText(f"Damaged-Deformed Count: {self.deformed_count}")
        self.open_label.setText(f"Damaged-Open Count: {self.open_count}")

        self.append_log(sorting_msg)

        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)
        self.table_widget.setItem(row_position, 0, QTableWidgetItem(timestamp))
        self.table_widget.setItem(row_position, 1, QTableWidgetItem(result))
        self.table_widget.setItem(row_position, 2, QTableWidgetItem(details))

        # Insert data into the database
        self.db.insert_result(timestamp, result, details)

        self.detection_data[result].append(1)
        if self.graph_window:
            self.graph_window.update_data({result: 1})

        if self.consecutive_defective_count >= 10:
            print("Triggering warning message...")
            self.show_warning_message()
            self.stop_detection()
            self.consecutive_defective_count = 0  # Reset the count after stopping detection

    def show_warning_message(self):
        warning_msg = "Warning: 10 consecutive defective items detected. Detection has been stopped."
        QMessageBox.warning(self, "Defect Detection Warning", warning_msg)

    def append_log(self, message: str):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def start_webcam_detection(self):
        self.start_detection(source=0)

    def start_file_detection(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Video File")
        if file_path:
            self.start_detection(source=file_path)

    def start_detection(self, source):
        if self.detection_thread and self.detection_thread.isRunning():
            self.stop_detection()

        self.detection_thread = DetectionThread(source, "models/best.pt")
        self.detection_thread.frame_processed.connect(self.update_display)
        self.detection_thread.detection_result.connect(self.update_counters)
        self.detection_thread.log_message.connect(self.append_log)
        self.detection_thread.start()

    def stop_detection(self):
        if self.detection_thread:
            self.detection_thread.stop()
            self.detection_thread = None
            self.append_log("Detection stopped.")

    def pause_detection(self):
        if self.detection_thread:
            self.detection_thread.toggle_pause()

    def resume_detection(self):
        if self.detection_thread:
            self.detection_thread.toggle_pause()

    def export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "CSV Files (*.csv)")
        if file_path:
            # Fetch all data from the database
            results = self.db.fetch_all_results()
            with open(file_path, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Status", "Details"])
                for row in results:
                    writer.writerow(row)  # Write the timestamp, status, and details
            self.append_log(f"✅ Report saved to {file_path}.")

    def open_graph_window(self):
        try:
            if not self.graph_window:
                self.graph_window = GraphWindow(self.detection_data)
            self.graph_window.show()
        except Exception as e:
            print(f"Error opening graph window: {e}")
            traceback.print_exc()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.full_screen_mode:
                self.showNormal()
                self.full_screen_mode = False
            else:
                self.showFullScreen()
                self.full_screen_mode = True
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Close the database connection when the application is closed
        self.db.close()
        event.accept()
