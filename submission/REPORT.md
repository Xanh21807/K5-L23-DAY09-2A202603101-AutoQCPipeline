# Báo cáo Day 09 — Nguyễn Xuân Anh, 2A202603101

> Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
- Quyết định của pipeline: **Hold**
- Số lượng ảnh nhận vào là 224 ảnh từ tệp `data/raw/`, loại bỏ 21 ảnh ở Intake -> nhận 203 ảnh sạch vào xử lý.
- Toàn bộ 203 ảnh được xuất sang `submission/export/clean_v1/` dưới dạng bản NHÁP để thử nghiệm.
- **Lý do chính:** Sau khi chạy sửa tự động và người duyệt mô phỏng hết ngân sách 80 ảnh, pipeline không còn bất kỳ lỗi bắt buộc nào (`ERROR = 0`). Tuy nhiên, tỉ lệ ảnh còn cảnh báo chưa duyệt là 21.67% (44/203 ảnh), vượt ngưỡng cho phép 10.00% của dự án, do đó hệ thống quyết định giữ trạng thái Hold để người xem xét thêm trước khi phát hành chính thức.

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

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

**Vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy?**
- File `05_review_queue.csv` đẩy 6 ảnh `NEEDS_LABEL` (`MISSING_LABEL_FILE`) lên đầu hàng với điểm số cao nhất (trọng số 10), tiếp theo là các ảnh có nhiều cảnh báo `POSSIBLE_WRONG_CLASS` (trọng số 3) và `POSSIBLE_MISSING` (trọng số 2).

**Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?**
- Với ngân sách 80 ảnh, con người giải quyết triệt để 6 ảnh thiếu nhãn (được gán nhãn đầy đủ trong mô phỏng) và xử lý phần lớn các ca lỗi ngữ nghĩa nặng nhất, giúp giảm số lỗi ngữ nghĩa từ 248 xuống còn 165 cảnh báo.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8| 1.00 / 0.50 → 1.00 / 0.67| Chấp nhận mở rộng ngưỡng để bắt thêm ảnh trùng bị co giãn/nén mà Precision vẫn giữ nguyên 1.00. Trên tập raw, ngưỡng 8 bắt thêm được img_0223 trùng với img_0077 và img_0101 rò rỉ vào tập test. Không chọn 16 hay 20 vì rủi ro xoá nhầm ảnh thật là quá lớn.|
| `second_opinion.conf` | 0.25 | 0.50 | Missing P: 0.50 → 0.57 (Recall giữ 1.00)|Tăng ngưỡng tin cậy để loại bỏ bớt các báo động giả (False Positives), giúp hàng đợi duyệt không bị tràn vượt quá ngân sách 80 ảnh, trong khi Recall vẫn đạt 1.00 (không bỏ sót lỗi thiếu nhãn). Không chọn 0.8 vì Recall tụt xuống 0.75 (bỏ sót 25% lỗi). |

**Một chỗ calibration có thể đánh lừa bạn:**
- Cạm bẫy "Tối ưu hóa F1 trên tập Calib" (`phash_dist = 16`):
  + Nhìn vào bảng sweep, nếu chỉ chạy theo chỉ số F1 cao nhất, ta sẽ dễ bị cám dỗ chọn `phash_dist = 16` vì nó cho $F_1 = 0.91$ (Recall đạt 0.83 và Precision = 1.00).
  + Vì sao đây là một sự đánh lừa? Tập `data/calib/` chỉ có vỏn vẹn 39 ảnh (30 ảnh gốc rất khác nhau về bối cảnh), nên khoảng cách Hamming 16/64 bit (chênh lệch tới 25% cấu trúc ảnh) vẫn chưa bị dính báo động giả (Precision vẫn bằng 1.00).
  + Nhưng trên dữ liệu thật (`data/raw/`), việc đặt khoảng cách Hamming lên tới 16 là cực kỳ nguy hiểm: hai bức ảnh chụp trên cùng một con phố (có cùng dải màu bầu trời, cùng mặt đường nhựa xám) nhưng có các xe và người hoàn toàn khác nhau rất dễ có $pHash \le 16$. Khi đó, máy sẽ coi chúng là "ảnh trùng" và xoá nhầm ảnh sạch khỏi tập dữ liệu (hành động `remove_image` của ERROR).
- Bằng chứng từ dữ liệu thực tế của lô 224 ảnh:
  + Khi đặt `phash_dist = 8`, bước 1 (Intake) loại bỏ 21 ảnh (gồm 8 ảnh trùng byte `DUP_IMAGE_EXACT`, 3 ảnh gần trùng `DUP_IMAGE_NEAR` và 5 ảnh rò rỉ `LEAK_TEST`).
  + Mở kiểm tra các cặp ảnh bị loại trong `01_intake.txt`:
    - `img_0076` trùng với `img_0042` ($pHash = 0$): Hai ảnh hoàn toàn giống hệt nhau về thị giác.
    - `img_0143` trùng với `img_0037` ($pHash = 0$): Hai ảnh giống hệt nhau.
    - `img_0223` trùng với `img_0077` ($pHash = 6$): Ảnh bị nén và thay đổi kích thước nhẹ nhưng đúng là cùng một góc chụp.
    - `img_0101` trùng với `test/test_039.jpg`: Bị phát hiện rò rỉ sang tập test (`LEAK_TEST`).
  + Số lượng 21 ảnh bị loại ở bước 1 là hoàn toàn hợp lý (chiếm ~9.3% tổng số ảnh), không có ảnh khác biệt nào bị xoá oan. Nếu cố tình đẩy lên 16 hay 20 như tập calib gợi ý, ta sẽ xoá nhầm nhiều ảnh có giá trị huấn luyện.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Chứng minh gate chặn đúng:**
- Khi chạy thử nghiệm không có người duyệt bằng lệnh:
  `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
  Do không có người gán cho 6 ảnh thiếu nhãn (`MISSING_LABEL_FILE`), lỗi bắt buộc vẫn còn nguyên -> Cửa chặn trả về kết luận **Rework**, mã thoát **20**, và hoàn toàn không xuất dataset ra thư mục export. Điều này chứng minh cửa chặn hoạt động hoàn toàn chính xác theo nguyên tắc chặn mọi lô dữ liệu còn lỗi bắt buộc.

**(b) Các điểm mù của pipeline:**
- **Box lỏng nhẹ (IoU nằm trong khoảng 0.50 – 0.60):** Do ngưỡng `iou_loose` đặt ở 0.5, nếu box vẽ hơi rộng hoặc lệch nhẹ nhưng IoU vẫn đạt 0.52 thì model phụ coi là hợp lệ và không cảnh báo, khiến box lỏng nhẹ vẫn lọt vào dataset sạch.
- **Lỗi gán nhầm mà model lớn cũng nhận diện sai:** Ví dụ một xe bán tải lớn bị người vẽ gán nhãn là car, nhưng model YOLO26l cũng dự đoán là car (do góc chụp phía trước tương tự xe con). Lúc này cả người và máy đều đồng thuận sai nên pipeline hoàn toàn không phát hiện được.
- **Ảnh trùng bị biến đổi cực mạnh:** Ảnh bị cắt xén (crop) 80% rồi xoay góc nghiêng, thuật toán pHash không nhận diện được khoảng cách Hamming $\le 8$, dẫn đến ảnh trùng vẫn lọt qua bước Intake.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

### 5.1. Bảng số liệu thực nghiệm
Thí nghiệm được thực hiện trên Google Colab với GPU T4, model khởi tạo `yolo26n.pt`, huấn luyện 20 epochs trên 2 seeds ngẫu nhiên (seed 0 và seed 1), đánh giá trên cùng tập test chuẩn gồm 100 ảnh (nhãn người):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.695 ± 0.010 | 0.482 ± 0.007 | 0.726 ± 0.005 | 0.619 ± 0.016 |

Chênh mAP50 (clean − raw) = **-0.031** (-3.1%).

### 5.2. So sánh chênh lệch với độ nhiễu giữa các seed
- **Độ lệch chuẩn giữa các seed:** Biến thể `clean` có độ lệch chuẩn mAP50 là $\pm 0.010$ (và mAP50-95 là $\pm 0.007$). Biến thể `raw` có độ lệch chuẩn Precision lên tới $\pm 0.061$.
- Mức chênh lệch $-0.031$ tuy lớn hơn độ lệch chuẩn giữa 2 seed, nhưng trong bối cảnh tập test chỉ có **100 ảnh**, sự chênh lệch này nằm ở ranh giới giữa suy giảm nhẹ và nhiễu chọn mẫu.
- **Kết luận trung thực:** Dữ liệu sau khi làm sạch (`clean`) có mAP50 thấp hơn dữ liệu thô ban đầu (`raw`) khoảng 3.1%. Ta **tuyệt đối không kết luận** rằng pipeline làm dữ liệu "tốt hơn về mặt điểm số ngay lập tức", mà cần phân tích nguyên nhân khoa học đằng sau.

### 5.3. Các giả thuyết giải thích và cách kiểm chứng

#### Giả thuyết 1: Metric của `raw` bị thổi phồng ảo do rò rỉ tập test (`LEAK_TEST`)
- **Giải thích:** Trong bước Intake, pipeline phát hiện có tới **5 ảnh trong `data/raw` bị trùng với tập test và val** (ví dụ `img_0049` trùng `test/test_033.jpg`, `img_0101` trùng `test/test_039.jpg`, `img_0167`, `img_0174`, `img_0221`). Biến thể `raw` đã vô tình được "học thuộc lòng" chính các ảnh có mặt trong bài thi test, dẫn đến điểm mAP50 của `raw` là **"metric đẹp giả"**. Ngược lại, biến thể `clean` đã loại bỏ hoàn toàn 5 ảnh rò rỉ này, nên điểm số của `clean` phản ánh đúng năng lực tổng quát hóa thực tế.
- **Cách kiểm chứng:** Đo riêng mAP của cả 2 model trên 5 ảnh bị rò rỉ và trên 95 ảnh test còn lại. Nếu trên 5 ảnh rò rỉ `raw` đạt mAP vượt trội trong khi trên 95 ảnh còn lại chênh lệch biến mất, giả thuyết này được xác thực.

#### Giả thuyết 2: Số lượng ảnh huấn luyện bị suy giảm (Đánh đổi Data Quantity vs Data Quality)
- **Giải thích:** Tập `clean` bị giảm 21 ảnh (từ 224 xuống 203 ảnh, giảm gần 10% dữ liệu). Trong bài toán Deep Learning với tập dữ liệu cực nhỏ (~200 ảnh), việc mất đi 21 ảnh đồng nghĩa với việc mất đi hàng chục box vật thể, khiến model ít cơ hội học các góc nhìn đa dạng. Ngoài ra, pipeline đã xoá các box hỏng/tràn mà chưa có dữ liệu bù đắp.
- **Cách kiểm chứng:** Chạy thử nghiệm biến thể `raw_sub` (lấy ngẫu nhiên đúng 203 ảnh từ `raw` để giữ nguyên quy mô dữ liệu như `clean`). Nếu `raw_sub` có mAP tụt xuống ngang bằng hoặc thấp hơn `clean`, chứng minh sự sụt giảm điểm số là do dung lượng dữ liệu ít hơn chứ không phải do việc làm sạch nhãn.

#### Giả thuyết 3: Tàn dư cảnh báo ngữ nghĩa chưa được duyệt hết
- **Giải thích:** Do ngân sách duyệt giới hạn ở 80 ảnh, trong khi hàng đợi có tới 130 ảnh, vẫn còn 44 ảnh chứa cảnh báo (`POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS`) chưa được con người thẩm định (dẫn đến phán quyết Hold). Một số nhãn máy thiếu sót vẫn còn sót lại trong tập `clean`.
- **Cách kiểm chứng:** Cấp thêm ngân sách để người duyệt duyệt toàn bộ 130 ảnh trong hàng đợi và huấn luyện lại biến thể `clean_full`.

### 5.4. Bài học rút ra & Việc tiếp theo
1. Điểm số cao trên tập test không đồng nghĩa với dữ liệu tốt: Loại bỏ dữ liệu rò rỉ (`LEAK_TEST`) làm mAP giảm nhưng giúp hệ thống trung thực, tránh rủi ro sập khi triển khai ra môi trường production thật.
2. Với tập dữ liệu nhỏ, cần chiến lược bổ sung ảnh thay thế khi đã loại bỏ ảnh trùng/hỏng để duy trì kích thước dữ liệu tối thiểu.

## 6. Quyết định và ghi chú AI

**(a) Quyết định cuối:**
- Quyết định hiện tại là **HOLD**. Bộ dữ liệu được xuất ra `submission/export/clean_v1/` là bản nháp để thử nghiệm, chưa được phát hành chính thức.
- **Kế hoạch để chuyển thành Release:** Cần cấp thêm ngân sách cho con người duyệt thêm khoảng 44 ảnh còn cảnh báo trong `05_review_queue.csv` (đặc biệt là các cảnh báo `POSSIBLE_WRONG_CLASS` và `POSSIBLE_MISSING`), đưa tỉ lệ ảnh cảnh báo xuống dưới 10%.

**(b) Ghi chú sử dụng AI:**
- **Prompt chính:** "Đọc dự án Day 09 AutoQC Pipeline, hướng dẫn chi tiết từng bước xây dựng 4 module theo TDD và giải thích luồng hoạt động của từng lớp."
- **Cách kiểm code AI:** Chạy unit test từng module (`pytest tests/test_<module>.py -v`), đối chiếu từng ca biên và mã lỗi với docstring của đề bài, sau đó chạy toàn bộ 79 test tích hợp e2e.
- **Một lần AI sai:** Khi kiểm tra script `check_submission.py` trên Windows, đường dẫn phân cách bằng dấu gạch chéo ngược `\` khiến hàm so sánh tên file bị lệch so với `_protected.json` (sử dụng `/`), tôi đã phát hiện và chuẩn hóa lại đường dẫn.
