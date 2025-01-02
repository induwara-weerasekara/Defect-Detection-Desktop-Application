import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from ultralytics import YOLO
import torch
import time


class DetectionThread(QThread):
    frame_processed = pyqtSignal(QPixmap)
    detection_result = pyqtSignal(str)
    log_message = pyqtSignal(str)
    detection_summary = pyqtSignal(dict)
    warning_signal = pyqtSignal(str)
    pause_trigger = pyqtSignal(str)

    def __init__(self, source, model_path, confidence=0.5, frame_skip=1):
        super().__init__()
        self.source = source
        self.confidence = confidence
        self.frame_skip = frame_skip
        self.running = False
        self.paused = False
        self.consecutive_damaged_count = 0
        self.line_y_position = None  # Removed default horizontal line position for flexibility

        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = YOLO(model_path)
            self.log_message.emit(f"Model loaded successfully on {self.device}.")
        except Exception as e:
            self.model = None
            self.log_message.emit(f"Error loading YOLO model: {e}")

    def run(self):
        if not self.model:
            self.log_message.emit("Detection cannot start. Model not loaded.")
            return

        self.running = True
        cap = cv2.VideoCapture(self.source)

        if not cap.isOpened():
            self.log_message.emit("Error: Could not open video source.")
            return

        frame_count = 0

        while self.running:
            if self.paused:
                continue

            ret, frame = cap.read()
            if not ret:
                self.log_message.emit("End of video or failed to grab frame.")
                break

            if frame_count % self.frame_skip != 0:
                frame_count += 1
                continue

            try:
                start_time = time.time()

                # Resize frame for better visualization in the display area
                frame = cv2.resize(frame, (800, 600))  # Adjust size as necessary

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                results = self.model.predict(
                    source=frame_rgb,
                    conf=self.confidence,
                    device=self.device,
                    agnostic_nms=True,
                    verbose=False
                )
                annotated_frame = self.annotate_frame(frame_rgb, results[0].boxes)

                height, width, channels = annotated_frame.shape
                qt_image = QImage(
                    annotated_frame.data, width, height,
                    channels * width, QImage.Format_RGB888
                )
                pixmap = QPixmap.fromImage(qt_image)
                self.frame_processed.emit(pixmap)

                damaged, intact = self.count_detections(results[0].boxes)
                self.handle_detections(damaged, intact)

                elapsed_time = time.time() - start_time
                self.detection_summary.emit({
                    "frame_count": frame_count,
                    "objects_detected": len(results[0].boxes),
                    "processing_time": elapsed_time,
                    "damaged": damaged,
                    "intact": intact,
                })

            except Exception as e:
                self.log_message.emit(f"Error during detection: {e}")
                break

            frame_count += 1

        cap.release()
        self.log_message.emit("Video source released. Detection thread stopped.")

    def annotate_frame(self, frame, boxes):
        """Annotates the frame with detection results and adds a horizontal line."""
        # Draw the horizontal line
        if self.line_y_position is None:
            self.line_y_position = frame.shape[0] // 2  # Default to the center of the frame

        line_color = (0, 255, 255)  # Yellow line
        line_thickness = 2
        cv2.line(frame, (0, self.line_y_position), (frame.shape[1], self.line_y_position), line_color, line_thickness)

        # Annotate bounding boxes
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])  # Get bounding box coordinates
            confidence = float(box.conf[0])  # Confidence score
            cls = int(box.cls[0])  # Class ID

            label = "Damaged" if cls == 0 else "Intact"
            color = (255, 0, 0) if cls == 0 else (0, 255, 0)  # Red for damaged, green for intact

            display_text = f"{label}: {confidence:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame, display_text, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )
        return frame

    def count_detections(self, boxes):
        damaged = sum(1 for box in boxes if int(box.cls) == 0)
        intact = sum(1 for box in boxes if int(box.cls) == 1)
        return damaged, intact

    def handle_detections(self, damaged, intact):
        if damaged > 0:
            self.consecutive_damaged_count += damaged
            if self.consecutive_damaged_count >= 10:
                self.warning_signal.emit("Warning: 10 consecutive damaged items detected. Pausing detection.")
                self.pause_trigger.emit("paused")
                self.paused = True
                self.consecutive_damaged_count = 0
        else:
            self.consecutive_damaged_count = 0

        for _ in range(damaged):
            self.detection_result.emit("Damaged")
        for _ in range(intact):
            self.detection_result.emit("Intact")

    def stop(self):
        self.running = False
        self.wait()

    def toggle_pause(self):
        self.paused = not self.paused
        state = "paused" if self.paused else "resumed"
        self.log_message.emit(f"Detection thread {state}.")
