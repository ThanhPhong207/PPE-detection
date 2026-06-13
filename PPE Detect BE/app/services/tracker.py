import time
import requests
import threading
import cv2
import base64
from core.config import settings

# Tránh crash hệ thống nếu thư viện cloudinary chưa được cài đặt
try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None

class ViolationTracker:
    def __init__(self, camera_id: int, detector_constants=None):
        self.camera_id = camera_id
        self.detector_constants = detector_constants
        
        # Trạng thái theo dõi thời gian và debounce
        self.violation_start = None
        self.clear_since = None
        self.last_reported_time = 0
        self.current_violation_start_time = None
        
        # Thiết lập cấu hình Cloudinary nếu được cung cấp credentials
        if cloudinary and settings.CLOUDINARY_CLOUD_NAME:
            cloudinary.config(
                cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                api_key=settings.CLOUDINARY_API_KEY,
                api_secret=settings.CLOUDINARY_API_SECRET
            )

    def analyze_violations(self, boxes, current_frame, active_rules):
        # 1. Phân loại đối tượng: Người và Trang bị bảo hộ
        persons = []
        gears = []
        
        for box in boxes:
            name = box["name"]
            conf = box["confidence"]
            bbox = box["bbox"]
            
            if name == 'Person':
                persons.append({'box': bbox, 'gear': []})
            elif name in ['Hardhat', 'Mask', 'Safety Vest', 'NO-Hardhat', 'NO-Mask', 'NO-Safety Vest']:
                cx = (bbox[0] + bbox[2]) / 2.0
                cy = (bbox[1] + bbox[3]) / 2.0
                gears.append({'name': name, 'conf': conf, 'box': bbox, 'c': (cx, cy)})

        # 2. Gán các trang bị bảo hộ cho đúng người (Containment Assignment)
        # Duyệt gears từ độ tin cậy cao xuống thấp để ưu tiên gán chính xác
        for g in sorted(gears, key=lambda x: -x['conf']):
            candidates = []
            for p in persons:
                ax, ay, bx, by = g['box']
                apx, apy, bpx, bpy = p['box']
                
                # Tính diện tích phần giao nhau (intersection area)
                x1 = max(ax, apx)
                y1 = max(ay, apy)
                x2 = min(bx, bpx)
                y2 = min(by, bpy)
                
                inter_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                gear_area = max(0.0, bx - ax) * max(0.0, by - ay)
                
                containment = inter_area / max(gear_area, 1e-6)
                candidates.append((containment, p))
                
            if not candidates:
                continue
                
            max_c = max(c for c, _ in candidates)
            if max_c < 0.5:  # CONTAINMENT_THRESHOLD = 0.5
                continue
                
            # Chọn người có khoảng cách tâm ngắn nhất nếu độ giao nhau gần tương đồng
            gc = g['c']
            near = [p for c, p in candidates if max_c - c <= 0.05]
            best_p = min(
                near, 
                key=lambda p: (gc[0] - ((p['box'][0] + p['box'][2])/2.0))**2 + (gc[1] - ((p['box'][1] + p['box'][3])/2.0))**2
            )
            best_p['gear'].append(g)

        # 3. Phân tích vi phạm trên từng cá nhân
        # Ánh xạ tên giao diện -> (class model khẳng định, class model phủ định, mã lỗi API)
        item_map = {
            'hardhat': ('Hardhat', 'NO-Hardhat', 'NO_HARDHAT'),
            'vest': ('Safety Vest', 'NO-Safety Vest', 'NO_SAFETY_VEST'),
            'mask': ('Mask', 'NO-Mask', 'NO_MASK'),
        }

        frame_missing = set()
        any_violating = False
        
        for p in persons:
            for rule_key, rule_active in active_rules.items():
                if not rule_active:
                    continue
                
                pos_name, neg_name, violation_code = item_map[rule_key]
                
                pos_conf = max([g['conf'] for g in p['gear'] if g['name'] == pos_name], default=None)
                neg_conf = max([g['conf'] for g in p['gear'] if g['name'] == neg_name], default=None)
                
                is_missing = False
                if neg_conf is not None and (pos_conf is None or neg_conf >= pos_conf):
                    is_missing = True
                elif pos_conf is not None and (neg_conf is None or pos_conf > neg_conf):
                    is_missing = False
                else:
                    is_missing = True  # fail-closed: không tín hiệu nào -> coi là thiếu
                    
                if is_missing:
                    any_violating = True
                    frame_missing.add(violation_code)

        # 4. Áp dụng cơ chế Debounce thời gian để lọc nhiễu nhấp nháy
        now = time.time()
        confirmed = False
        
        if any_violating:
            self.clear_since = None
            if self.violation_start is None:
                self.violation_start = now
                self.current_violation_start_time = time.time()
        else:
            if self.violation_start is not None:
                if self.clear_since is None:
                    self.clear_since = now
                # Ân hạn reset (Grace Period) chống rớt box nhất thời
                if now - self.clear_since >= 0.5:
                    self.violation_start = None
                    self.clear_since = None
                    self.current_violation_start_time = None

        if self.violation_start is not None:
            elapsed = now - self.violation_start
            if elapsed >= settings.VIOLATION_THRESHOLD_SECONDS:
                confirmed = True

        status = "Danger" if confirmed else "Safe"
        current_violations = sorted(list(frame_missing)) if confirmed else []
        
        # 5. Gửi báo cáo bất đồng bộ sang API Spring Boot & Cloudinary
        if confirmed and current_violations:
            if now - self.last_reported_time >= settings.COOLDOWN_DUPLICATE_SECONDS:
                self.last_reported_time = now
                threading.Thread(
                    target=self.report_violation,
                    args=(current_violations, current_frame, self.current_violation_start_time, time.time()),
                    daemon=True
                ).start()

        return status, current_violations

    def report_violation(self, violations, frame, start_time, end_time):
        print(f"[Violation Tracker] Báo cáo vi phạm {violations} cho camera {self.camera_id}")
        
        image_url = None
        if cloudinary and settings.CLOUDINARY_CLOUD_NAME:
            try:
                _, encoded_image = cv2.imencode('.jpg', frame)
                base64_data = base64.b64encode(encoded_image).decode('utf-8')
                upload_str = f"data:image/jpeg;base64,{base64_data}"
                
                upload_result = cloudinary.uploader.upload(
                    upload_str,
                    folder="ppe_violations",
                    resource_type="image"
                )
                image_url = upload_result.get("secure_url")
                print(f"[Violation Tracker] Upload Cloudinary thành công: {image_url}")
            except Exception as e:
                print(f"[Violation Tracker] Lỗi upload Cloudinary: {e}")

        iso_start = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(start_time))
        iso_end = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(end_time))
        duration = int(end_time - start_time)

        # Gửi cả hai dạng key (số nhiều & số ít) để tương thích tối đa với DTO Spring Boot
        payload = {
            "cameraId": self.camera_id,
            "violationUrl": image_url,
            "violationType": violations,
            "violationTypes": violations,
            "startTime": iso_start,
            "endTime": iso_end,
            "durationSeconds": duration
        }

        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(settings.SPRING_BOOT_API_URL, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                print(f"[Violation Tracker] Đã lưu báo cáo vi phạm. Status code: {response.status_code}")
            else:
                print(f"[Violation Tracker] Server trả lỗi khi lưu báo cáo: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[Violation Tracker] Không thể kết nối Spring Boot API: {e}")
