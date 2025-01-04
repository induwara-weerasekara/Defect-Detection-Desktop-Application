from PyQt5.QtWidgets import (
    QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import datetime
import csv
from detection import DetectionThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Defect Detection Application")
        self.setGeometry(100, 100, 1200, 800)

        # Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Video Display Area
        self.video_label = QLabel()
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.video_label, stretch=6)

        # Counter and Log Section
        self.stats_layout = QVBoxLayout()

        # Counter Layout
        self.counter_layout = QHBoxLayout()
        self.total_label = QLabel("Total Count: 0")
        self.damaged_label = QLabel("Damaged Count: 0")
        self.intact_label = QLabel("Intact Count: 0")
        for label in [self.total_label, self.damaged_label, self.intact_label]:
            label.setStyleSheet("font-size: 16px; padding: 5px;")
            self.counter_layout.addWidget(label)
        self.stats_layout.addLayout(self.counter_layout)

        # Log Area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #f1f1f1; font-size: 14px;")
        self.log_area.setFixedHeight(100)
        self.stats_layout.addWidget(self.log_area)

        self.main_layout.addLayout(self.stats_layout, stretch=2)

        # Buttons Section
        self.button_layout = QHBoxLayout()
        self.create_button("Start Webcam", "#4CAF50", self.start_webcam_detection)
        self.create_button("Select File", "#008CBA", self.start_file_detection)
        self.create_button("Pause", "#FFC107", self.pause_detection)
        self.create_button("Resume", "#4CAF50", self.resume_detection)
        self.create_button("Stop", "#f44336", self.stop_detection)
        self.create_button("Export Report", "#673AB7", self.export_report)
        self.create_button("Open Graph", "#FF5722", self.open_graph_window)
        self.main_layout.addLayout(self.button_layout, stretch=1)

        # Table Section
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Timestamp", "Status", "Details"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.setFixedHeight(120)
        self.main_layout.addWidget(self.table_widget, stretch=2)

        # Detection Thread Variables
        self.detection_thread = None
        self.total_count = 0
        self.damaged_count = 0
        self.intact_count = 0
        self.graph_window = None

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
        if result not in ["Damaged", "Intact"]:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details = "Defective item detected." if result == "Damaged" else "Non-defective item."

        if result == "Damaged":
            self.damaged_count += 1
        else:
            self.intact_count += 1
        self.total_count += 1

        self.total_label.setText(f"Total Count: {self.total_count}")
        self.damaged_label.setText(f"Damaged Count: {self.damaged_count}")
        self.intact_label.setText(f"Intact Count: {self.intact_count}")

        # Update table
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)
        self.table_widget.setItem(row_position, 0, QTableWidgetItem(timestamp))
        self.table_widget.setItem(row_position, 1, QTableWidgetItem(result))
        self.table_widget.setItem(row_position, 2, QTableWidgetItem(details))

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

    def pause_detection(self):
        if self.detection_thread:
            self.detection_thread.toggle_pause()

    def resume_detection(self):
        if self.detection_thread:
            self.detection_thread.toggle_pause()

    def export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "CSV Files (*.csv)")
        if file_path:
            with open(file_path, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Status", "Details"])
                for row in range(self.table_widget.rowCount()):
                    timestamp = self.table_widget.item(row, 0).text()
                    status = self.table_widget.item(row, 1).text()
                    details = self.table_widget.item(row, 2).text()
                    writer.writerow([timestamp, status, details])
            self.append_log(f"Report saved to {file_path}.")

    def open_graph_window(self):
        if not self.graph_window:
            self.graph_window = GraphWindow()
        self.graph_window.show()
