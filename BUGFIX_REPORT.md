# Báo cáo kiểm tra & sửa lỗi — PPE Detection App

**Phạm vi:** `PPE APP/` (ứng dụng desktop giám sát PPE bằng YOLO).
**File thay đổi:** `PPE APP/main.py` (sửa logic) + xoá 3 file mồ côi.

---

## 1. 🔴 Bug chính: Nhận diện sai khi có NHIỀU người (false-SAFE)

### Triệu chứng
Người A mặc đủ đồ bảo hộ, người B không mặc gì → hệ thống vẫn báo **AN TOÀN (SAFE)**.

### Nguyên nhân gốc
Logic cũ trong `detect_and_check` gom mọi vật thể của **cả khung hình** vào một tập chung rồi chỉ hỏi *"trong ảnh có tồn tại Hardhat/Safety Vest nào không?"*:

```python
detected_classes = set()
...
detected_classes.add(name)            # gom đồ của MỌI người vào 1 set
...
for item in required_items:
    if found_person and item not in detected_classes:   # chỉ kiểm tra mức TOÀN ẢNH
        violations.append(item)
```

→ Chỉ cần **một** người mặc đủ là `set` đã chứa `Hardhat`, `Safety Vest`, nên không item nào bị coi là thiếu → **một người mặc đủ "che" cho tất cả người còn lại**.

Ngoài ra, model `weights/best.pt` đã được train sẵn các class phát hiện vi phạm **trực tiếp** (`NO-Hardhat`, `NO-Mask`, `NO-Safety Vest`) nhưng code **bỏ qua hoàn toàn**, thay vào đó tự suy luận "thiếu = không thấy" — kém chính xác.

> Class của model: `Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Vest`

### Cách sửa — tách 2 tầng độc lập

**a) Tầng KHÔNG GIAN (gốc của bug):** kiểm tra **từng người độc lập**.
- Tách detections thành box `Person` và box đồ bảo hộ.
- Gán mỗi box đồ bảo hộ cho đúng **một người** theo độ chứa
  `containment = diện_tích_giao(gear, person) / diện_tích(gear)`, ngưỡng `0.5`
  (xét box conf cao trước; gần hoà thì chọn người có tâm gần nhất).
- Với mỗi người & mỗi item bắt buộc, quyết định theo bảng dùng đúng class `NO-*`:

  | Có đồ (pos) | Có `NO-*` (neg) | Kết luận |
  |:---:|:---:|---|
  | không | có | **Vi phạm** (tín hiệu `NO-*` model đã học) |
  | có | không | Đạt |
  | có | có | `NO-*` thắng nếu `neg ≥ pos`, ngược lại Đạt |
  | không | không | **Vi phạm** (fail-closed — không tín hiệu nào ⇒ coi là thiếu) |

  → Nhánh *"không tín hiệu nào → vi phạm"* chính là cái bắt được người ở trần.
- Khung hình UNSAFE nếu **bất kỳ** người nào vi phạm.

**b) Tầng THỜI GIAN (chống nhấp nháy):** một bộ đếm chung `violation_start`.
- Chỉ cần khung hình **liên tục có vi phạm** đủ `DEBOUNCE_SECONDS = 2s` thì mới báo động.
- **Không bám danh tính từng người** ⇒ người di chuyển không làm sai lệch (xem mục 3).
- Có **ân hạn reset** `RESET_GRACE = 0.5s`: detector rớt box 1–2 frame không làm mất thời gian đã tích luỹ.

**c) Vẽ nhất quán:** bỏ `r.plot()`, tự vẽ từng người — xanh `OK` / vàng `VERIFYING` / đỏ `MISSING` — màu box **luôn khớp** banner và `is_safe`.

---

## 2. Các lỗi khác đã sửa (cùng nằm trong `main.py`)

| # | Vấn đề | Cách sửa |
|---|--------|----------|
| 6 | `r.plot()` vẽ cả box `NO-Hardhat` nhưng logic bỏ qua → thấy box đỏ mà hệ thống báo SAFE | Tự vẽ box theo đúng trạng thái từng người, suy ra từ cùng cờ `confirmed` |
| 7 | Tiền xử lý `GaussianBlur → CLAHE → sharpen` mỗi frame: blur rồi sharpen tự triệt tiêu, tạo halo, giảm độ chính xác YOLO | Chỉ giữ `CLAHE` (cân bằng sáng), bỏ blur + sharpen |
| 8 | `os.startfile` mở Excel chỉ chạy trên Windows | Cross-platform (Windows / macOS `open` / Linux `xdg-open`) |
| — | **Ảnh tĩnh không bao giờ xác nhận vi phạm**: 1 lần gọi luôn `elapsed = 0 < 2s` ⇒ kẹt VERIFYING | Thêm cờ `still=True` (ảnh tĩnh) → xác nhận tức thì, bỏ qua debounce |

---

## 3. Quá trình review & loại bỏ hồi quy

Bản sửa được soát qua nhiều vòng review/verify đối kháng. Hai hồi quy được phát hiện và xử lý trước khi chốt:

1. **Bộ đếm theo từng người bằng lưới toạ độ** (phương án trung gian): người **di chuyển/jitter** đổi ô lưới mỗi frame → reset bộ đếm → kẹt VERIFYING → **false-SAFE quay lại**.
2. **Tracker bám người bằng IoU/khoảng-cách-tâm** (phương án trung gian thứ 2): vẫn lọt người nhỏ/ở xa di chuyển nhanh, **và** đẻ thêm lỗi mới — người đạt đứng cạnh "cướp" track của người vi phạm rồi xoá bộ đếm.

→ **Kết luận thiết kế:** bug user báo là **không gian**, đã được tầng (a) xử lý triệt để mà *không cần* tracking. Tracking danh tính chỉ làm mong manh thêm và là *overkill* cho app 1–3 người. Vì vậy tầng thời gian quay về **một bộ đếm chung đơn giản + ân hạn** — robust với chuyển động, không có gì để "cướp".

---

## 4. Dọn file mồ côi

Xoá 3 file không được file nào import tới và đều hỏng:

| File | Lý do |
|------|-------|
| `PPE APP/detector.py` | Bản `PPEDetector` trùng lặp, gọi `ImageEnhancer.enhance_for_yolo()` — method không tồn tại |
| `PPE APP/ui_components.py` | Sai tên class (`Vest/Helmet/Shoes/Gloves`) ≠ tên model; `main.py` tự dựng UI riêng |
| `PPE APP/database.py` | Import `config.py` không tồn tại; lớp ghi MySQL đang dở (app dùng Excel thay thế) |

> Lịch sử git vẫn giữ — khôi phục bằng `git checkout <commit> -- <file>` nếu cần.

---

## 5. Kết quả kiểm thử

Test headless nạp detections có kiểm soát thẳng vào code `detect_and_check` thật:

| Kịch bản | Kết quả |
|----------|---------|
| A đủ đồ + B ở trần (đúng bug đã báo) | Logic cũ → `SAFE` (sai) · **Logic mới → `UNSAFE`, gắn vi phạm cho B độc lập** ✓ |
| Hai người đều đủ đồ | `SAFE` ✓ |
| Người vi phạm **di chuyển** qua các frame | Vẫn xác nhận sau ~2s (hết motion-false-SAFE) ✓ |
| **Rớt box 1 frame** xen giữa | Ân hạn giữ bộ đếm, không nhấp nháy ✓ |
| End-to-end model thật trên ảnh validation | Chạy không lỗi |

---

## 6. Hạn chế đã biết (chấp nhận — đều fail-safe)

- **Hai người chồng box gần kín nhau:** đồ bảo hộ có thể bị gán nhầm cho người bên cạnh → nhãn đỏ có thể vào nhầm người. **Verdict toàn cục vẫn đúng** (vẫn UNSAFE). Cần tracker thật mới xử lý triệt để — không cần thiết cho quy mô app này.
- **Một frame "sạch" giả** (model đọc nhầm tất cả là đạt) trong lúc đang DANGER: banner có thể nhấp nháy ≤ `RESET_GRACE` (0.5s) rồi báo lại — thiên về *cảnh báo nhiều hơn*, không bỏ sót.

---

## 7. Việc còn lại (chưa làm)

- **Backend `PPE Detect BE/` chưa chạy được:** thiếu `app/services/detector.py` và `app/services/tracker.py` (bị `ppe_stream.py` import nhưng không tồn tại) → `ImportError` khi khởi động. Logic per-person ở mục 1 có thể tái dùng để viết `analyze_violations` / `ViolationTracker`.

---

## Phụ lục — tham số chính (`PPE APP/main.py`)

| Hằng số | Giá trị | Ý nghĩa |
|---------|:------:|---------|
| `CONTAINMENT_THRESHOLD` | `0.5` | Tỉ lệ box đồ bảo hộ phải nằm trong box người để được gán |
| `DEBOUNCE_SECONDS` | `2.0` | Thời gian vi phạm liên tục trước khi báo động |
| `RESET_GRACE` | `0.5` | Ân hạn trước khi xoá bộ đếm (chịu dropout 1–2 frame) |
| conf YOLO | `0.4` | Ngưỡng tin cậy phát hiện |
