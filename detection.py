import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from ultralytics import YOLO
import torch
import time
import traceback

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
        self.line_y_position = None
        self.tracked_objects = {}

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

        if isinstance(self.source, str) and self.source.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            self.process_image(self.source)
        else:
            self.process_video()

    def process_image(self, image_path):
        try:
            frame = cv2.imread(image_path)
            if frame is None:
                self.log_message.emit(f"Error: Could not read image file {image_path}.")
                return

            frame = cv2.resize(frame, (800, 600))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = self.model.predict(
                source=frame_rgb,
                conf=self.confidence,
                device=self.device,
                agnostic_nms=True,
                verbose=False
            )

            if not results or len(results) == 0:
                self.log_message.emit("No detection results found.")
                return

            annotated_frame = self.annotate_frame(frame_rgb, results[0].boxes)

            height, width, channels = annotated_frame.shape
            qt_image = QImage(
                annotated_frame.data, width, height,
                channels * width, QImage.Format_RGB888
            )
            pixmap = QPixmap.fromImage(qt_image)
            self.frame_processed.emit(pixmap)

            class_counts = self.count_detections(results[0].boxes)
            self.handle_detections(class_counts)

            self.detection_summary.emit({
                "frame_count": 1,
                "objects_detected": sum(class_counts.values()),
                "processing_time": 0,
                **class_counts
            })

        except Exception as e:
            self.log_message.emit(f"Error during image processing: {e}")
            traceback.print_exc()

    def process_video(self):
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
                if isinstance(self.source, str):  # If it's a video file, restart it
                    cap.release()
                    cap = cv2.VideoCapture(self.source)
                    if not cap.isOpened():
                        self.log_message.emit("Error: Could not reopen video source.")
                        break
                    continue
                else:  # If it's a webcam, try reconnecting
                    cap.release()
                    cap = cv2.VideoCapture(self.source)
                    if not cap.isOpened():
                        self.log_message.emit("Error: Could not reconnect to webcam.")
                        break
                    continue

            if frame_count % self.frame_skip != 0:
                frame_count += 1
                continue

            try:
                start_time = time.time()

                frame = cv2.resize(frame, (800, 600))
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                results = self.model.predict(
                    source=frame_rgb,
                    conf=self.confidence,
                    device=self.device,
                    agnostic_nms=True,
                    verbose=False
                )

                if not results or len(results) == 0:
                    self.log_message.emit("No detection results found.")
                    continue

                annotated_frame = self.annotate_frame(frame_rgb, results[0].boxes)

                height, width, channels = annotated_frame.shape
                qt_image = QImage(
                    annotated_frame.data, width, height,
                    channels * width, QImage.Format_RGB888
                )
                pixmap = QPixmap.fromImage(qt_image)
                self.frame_processed.emit(pixmap)

                class_counts = self.count_detections(results[0].boxes)
                self.handle_detections(class_counts)

                elapsed_time = time.time() - start_time
                self.detection_summary.emit({
                    "frame_count": frame_count,
                    "objects_detected": sum(class_counts.values()),
                    "processing_time": elapsed_time,
                    **class_counts
                })

            except Exception as e:
                self.log_message.emit(f"Error during detection: {e}")
                traceback.print_exc()

            frame_count += 1

        cap.release()
        self.log_message.emit("Video source released. Detection thread stopped.")

    def annotate_frame(self, frame, boxes):
        if self.line_y_position is None:
            self.line_y_position = int(frame.shape[0] * 0.35)

        cv2.line(frame, (0, self.line_y_position), (frame.shape[1], self.line_y_position), (0, 255, 255), 2)
        current_frame_objects = {}

        class_names = ["Damaged-Open", "Damaged-Deformed", "Intact"]
        colors = [(255, 0, 0), (0, 0, 255), (0, 255, 0)]

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            cls = int(box.cls[0])

            if cls >= len(class_names):
                continue

            label = class_names[cls]
            color = colors[cls]
            display_text = f"{label}: {confidence:.2f}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            (text_width, text_height), _ = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - text_height - 10), (x1 + text_width, y1), color, -1)

            cv2.putText(
                frame, display_text, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
            )

            object_id = (x1 + x2) // 2
            current_frame_objects[object_id] = y2

            if object_id in self.tracked_objects:
                if self.tracked_objects[object_id] < self.line_y_position <= y2:
                    self.tracked_objects[object_id] = y2
                    self.log_message.emit(f"{label} object crossed the line.")
                    self.detection_result.emit(label)
            else:
                self.tracked_objects[object_id] = y2

        self.tracked_objects = {
            obj_id: y2 for obj_id, y2 in self.tracked_objects.items()
            if obj_id in current_frame_objects
        }

        return frame

    def count_detections(self, boxes):
        counts = {"Intact": 0, "Damaged-Deformed": 0, "Damaged-Open": 0}
        for box in boxes:
            cls = int(box.cls[0])
            if cls == 2:
                counts["Intact"] += 1
            elif cls == 1:
                counts["Damaged-Deformed"] += 1
            elif cls == 0:
                counts["Damaged-Open"] += 1
        return counts

    def handle_detections(self, class_counts):
        defective_count = class_counts["Damaged-Deformed"] + class_counts["Damaged-Open"]

        if defective_count > 0:
            self.consecutive_damaged_count += defective_count
            if self.consecutive_damaged_count >= 10:
                self.warning_signal.emit("Warning: 10 consecutive defective items detected. Pausing detection.")
                self.pause_trigger.emit("paused")
                self.paused = True
                self.consecutive_damaged_count = 0  # Reset the count after triggering the warning
        else:
            self.consecutive_damaged_count = 0

        for cls, count in class_counts.items():
            for _ in range(count):
                self.detection_result.emit(cls)

    def stop(self):
        self.running = False
        self.wait()

    def toggle_pause(self):
        self.paused = not self.paused
        self.log_message.emit(f"Detection thread {'paused' if self.paused else 'resumed'}.")
