# Báo cáo Day 09 — <Nguyễn Xuân Anh>, <2A202603101>

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).
-Quyết định của pipeline: Hold 
-Số lượng ảnh nhận vào là 224 ảnh từ tệp data/raw/ , loại bỏ 21 ảnh ở Intake -> nhận 203 ảnh sạch vào xử lý.
-Toàn bộ 203 ảnh được xuất sang submission/export/clean_v1/ dưới dạng bản NHÁP để thử nghiệm .
Lý do chính:
    -Sau khi chạy sửa tự động và người duyệt mô phỏng hết ngân sách 80 ảnh, pipeline không còn bất kỳ lỗi bắt buộc nào (ERROR = 0). Tuy nhiên, tỉ lệ ảnh còn cảnh báo chưa duyệt là 21.67% (44/203 ảnh), vượt ngưỡng cho phép 10.00% của dự án, do đó hệ thống quyết định giữ trạng thái Hold để người xem xét thêm trước khi phát hành chính thức.
## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.
## 2. Lỗi và phân việc
| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2 ảnh | Máy | Ảnh hỏng không đọc được byte, loại bỏ cơ học ở cửa vào |
| `BAD_SIZE` | 3 ảnh | Máy | Cạnh ngắn < 250px không đạt độ phân giải tối thiểu, loại bỏ ở cửa vào |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Trùng từng byte (MD5) với ảnh khác, loại bỏ ở cửa vào |
| `DUP_IMAGE_NEAR` | 3 ảnh | Máy | Trùng gần đúng qua pHash (khoảng cách $\le 8$), loại bỏ ở cửa vào |
| `LEAK_TEST` | 5 ảnh | Máy | Trùng với ảnh trong tập test/val, loại bỏ để tránh metric đẹp giả |
| `BAD_FORMAT` | 3 dòng | Máy | Dòng nhãn thiếu cột hoặc chứa nan/inf, tự động xoá dòng (`drop_line`) |
| `BAD_CLASS_ID` | 6 dòng | Máy | ID lớp lạ ngoài 0..3 (-1, 4, 93), tự động xoá dòng |
| `BOX_ZERO` | 4 dòng | Máy | Kích thước w <= 0 hoặc h <= 0, tự động xoá dòng |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy | Box tràn ra ngoài mép ảnh, tự động cắt về [0, 1] (`clip_box`) |
| `DUP_BOX` | 7 dòng | Máy | Hai box cùng lớp trùng đè lên nhau (IoU > 0.9), xoá box sau |
| `BAD_CLASS_NAME` | 2 dòng | Máy | Tên lớp trong `data.yaml` viết hoa (`Person`, `Bus`), tự động chuẩn hoá lại |
| `MISSING_LABEL_FILE` | 6 ảnh | **Người** | Máy không được tự ý bịa nhãn; xếp ưu tiên cao nhất để người gán |
| `POSSIBLE_WRONG_CLASS`| 22 box | **Người** | Cùng vị trí nhưng gán khác lớp (nghi vấn nhầm nhãn), chuyển người phân xử |
| `POSSIBLE_MISSING` | 152 box | **Người** | Model lớn phát hiện vật thể mà nhãn thiếu, chuyển người kiểm tra |
| `POSSIBLE_LOOSE_BOX` | 45 box | **Người** | Box vẽ bị lỏng/lệch (IoU < 0.5), chuyển người chỉnh lại |
| `POSSIBLE_FALSE_POS` | 29 dòng | **Người** | Nhãn vẽ không khớp vật nào model thấy (nghi vẽ thừa), chuyển người xem |
| `EMPTY_LABEL` | 12 ảnh | **Người** | File nhãn rỗng, chuyển người xác nhận là ảnh nền hay quên gán |
| `BOX_TINY` / `BOX_HUGE`| 9 dòng | **Người** | Box quá nhỏ (< 12px) hoặc quá lớn (> 95% ảnh), cảnh báo để người kiểm tra |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? 
    File `05_review_queue.csv` đẩy 6 ảnh NEEDS_LABEL (MISSING_LABEL_FILE) lên đầu hàng với điểm số cao nhất (trọng số 10), tiếp theo là các ảnh có nhiều cảnh báo POSSIBLE_WRONG_CLASS (trọng số 3) và POSSIBLE_MISSING (trọng số 2).
Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?
    Với ngân sách 80 ảnh, con người giải quyết triệt để 6 ảnh thiếu nhãn (được gán nhãn đầy đủ trong mô phỏng) và xử lý phần lớn các ca lỗi ngữ nghĩa nặng nhất, giúp giảm số lỗi ngữ nghĩa từ 248 xuống còn 165 cảnh báo.
## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8| 1.00 / 0.50 → 1.00 / 0.67| 	Chấp nhận mở rộng ngưỡng để bắt thêm ảnh trùng bị co giãn/nén mà Precision vẫn giữ nguyên 1.00. Trên tập raw, ngưỡng 8 bắt thêm được img_0223 trùng với img_0077 và img_0101 rò rỉ vào tập test. Không chọn 16 hay 20 vì rủi ro xoá nhầm ảnh thật là quá lớn.|
| `second_opinion.conf` | 0.25 | 0.50 | Missing P: 0.50 → 0.57 (Recall giữ 1.00)|Tăng ngưỡng tin cậy để loại bỏ bớt các báo động giả (False Positives), giúp hàng đợi duyệt không bị tràn vượt quá ngân sách 80 ảnh, trong khi Recall vẫn đạt 1.00 (không bỏ sót lỗi thiếu nhãn). Không chọn 0.8 vì Recall tụt xuống 0.75 (bỏ sót 25% lỗi). |

TODO(học viên): **một chỗ calibration có thể đánh lừa bạn**, kèm bằng chứng từ dữ liệu của bạn (vd. mở xem vài cặp ảnh bị cho là trùng; số ảnh bị loại ở bước 1 có hợp lý không?).
Cạm bẫy "Tối ưu hóa F1 trên tập Calib" (phash_dist = 16):
    +Nhìn vào bảng sweep, nếu chỉ chạy theo chỉ số F1 cao nhất, ta sẽ dễ bị cám dỗ chọn phash_dist = 16 vì nó cho F1 = 0.91 (Recall đạt 0.83 và Precision = 1.00)
    +Vì sao đây là một sự đánh lừa? Tập data/calib/ chỉ có vỏn vẹn 39 ảnh (30 ảnh gốc rất khác nhau về bối cảnh), nên khoảng cách Hamming 16/64
    bit (chênh lệch tới 25% cấu trúc ảnh) vẫn chưa bị dính báo động giả (Precision vẫn bằng 1.00).
    +Nhưng trên dữ liệu thật (data/raw/), việc đặt khoảng cách Hamming lên tới 16 là cực kỳ nguy hiểm: hai bức ảnh chụp trên cùng một con phố (có cùng dải màu bầu trời, cùng mặt đường nhựa xám) nhưng có các xe và người hoàn toàn khác nhau rất dễ có pHash <= 16. Khi đó , máy sẽ coi chúng là "ảnh trùng" và xoá nhầm ảnh sạch khỏi tập dữ liệu (hành động remove_image của ERROR).
Bằng chứng từ dữ liệu thực tế của lô 224 ảnh:
    +Khi đặt phash_dist = 8, bước 1 (Intake) loại bỏ 21 ảnh (gồm 8 ảnh trùng byte DUP_IMAGE_EXACT, 3 ảnh gần trùng DUP_IMAGE_NEAR và 5 ảnh rò rỉ LEAK_TEST).
    +Mở kiểm tra các cặp ảnh bị loại trong 01_intake.txt :
        -img_0076 trùng với img_0042 ( pHash = 0): Hai ảnh hoàn toàn giống hệt nhau về thị giác.
        -img_0143 trùng với img_0037 ( pHash = 0): Hai ảnh giống hệt nhau.
        -img_0223 trùng với img_0077( pHash = 0): Ảnh bị nén và thay đổi kích thước nhẹ nhưng đúng là cùng một góc chụp.
        -img_0101 trùng với test/test_039.jpg: Bị phát hiện rò rỉ sang tập test (LEAK_TEST).
    +Số lượng 21 ảnh bị loại ở bước 1 là hoàn toàn hợp lý (chiếm ~9.3% tổng số ảnh), không có ảnh khác biệt nào bị xoá oan. Nếu cố tình đẩy lên 16 hay 20 như tập calib gợi ý, ta sẽ xoá nhầm nhiều ảnh có giá trị huấn luyện.
## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

(a) Chứng minh gate chặn đúng:
    Khi chạy thử nghiệm không có người duyệt bằng lệnh: python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb Do không có người gán cho 6 ảnh thiếu nhãn (MISSING_LABEL_FILE), lỗi bắt buộc vẫn còn nguyên -> Cửa chặn trả về kết luận Rework, mã thoát 20, và hoàn toàn không xuất dataset ra thư mục export. Điều này chứng minh cửa chặn hoạt động hoàn toàn chính xác theo nguyên tắc chặn mọi lô dữ liệu còn lỗi bắt buộc.

(b) Các điểm mù của pipeline:
    +Box lỏng nhẹ (IoU nằm trong khoảng 0.50 – 0.60): Do ngưỡng iou_loose đặt ở 0.5, nếu box vẽ hơi rộng hoặc lệch nhẹ nhưng IoU vẫn đạt 0.52 thì model phụ coi là hợp lệ và không cảnh báo, khiến box lỏng nhẹ vẫn lọt vào dataset sạch.
    +Lỗi gán nhầm mà model lớn cũng nhận diện sai: Ví dụ một xe bán tải lớn bị người vẽ gán nhãn là car, nhưng model YOLO26l cũng dự đoán là car (do góc chụp phía trước tương tự xe con). Lúc này cả người và máy đều đồng thuận sai nên pipeline hoàn toàn không phát hiện được.
    +Ảnh trùng bị biến đổi cực mạnh: Ảnh bị cắt xén (crop) 80% rồi xoay góc nghiêng, thuật toán pHash không nhận diện được khoảng cách Hamming <= 8, dẫn đến ảnh trùng vẫn lọt qua bước Intake.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).
    Chưa chạy do máy GPU yếu 
TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
(a) Quyết định cuối:
    +Quyết định hiện tại là HOLD. Bộ dữ liệu được xuất ra submission/export/clean_v1/ là bản nháp để thử nghiệm, chưa được phát hành chính thức.
    +Kế hoạch để chuyển thành Release: Cần cấp thêm ngân sách cho con người duyệt thêm khoảng 44 ảnh còn cảnh báo trong 05_review_queue.csv (đặc biệt là các cảnh báo POSSIBLE_WRONG_CLASS và POSSIBLE_MISSING), đưa tỉ lệ ảnh cảnh báo xuống dưới 10%.

(b) Ghi chú sử dụng AI:
    +Prompt chính: "Đọc dự án Day 09 AutoQC Pipeline, hướng dẫn chi tiết từng bước xây dựng 4 module theo TDD và giải thích luồng hoạt động của từng lớp."
    +Cách kiểm code AI: Chạy unit test từng module (pytest tests/test_<module>.py -v), đối chiếu từng ca biên và mã lỗi với docstring của đề bài, sau đó chạy toàn bộ 79 test tích hợp e2e.
    +Một lần AI sai: Khi kiểm tra script check_submission.py trên Windows, đường dẫn phân cách bằng dấu gạch chéo ngược \ khiến hàm so sánh tên file bị lệch so với _protected.json (sử dụng /), tôi đã phát hiện và chuẩn hóa lại đường dẫn.