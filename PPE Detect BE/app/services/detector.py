import cv2
import numpy as np
from ultralytics import YOLO
from core.config import settings

class YOLODetector:
    def __init__(self):
        # Nạp mô hình YOLOv8 từ đường dẫn đã cấu hình
        self.model = YOLO(settings.MODEL_PATH)
        self.class_names = self.model.names

    def run_inference(self, frame):
        # Tiền xử lý ảnh sử dụng CLAHE (cân bằng độ tương phản thích nghi)
        proc = self.apply_clahe(frame)
        results = self.model(proc, stream=True, conf=0.4)
        
        boxes = []
        for r in results:
            for box in r.boxes:
                class_id = int(box.cls)
                name = self.class_names.get(class_id, "Unknown")
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf)
                boxes.append({
                    "bbox": xyxy,
                    "class_id": class_id,
                    "name": name,
                    "confidence": conf
                })
        return boxes

    @staticmethod
    def apply_clahe(frame):
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced_img = cv2.merge((l, a, b))
        return cv2.cvtColor(enhanced_img, cv2.COLOR_LAB2BGR)
