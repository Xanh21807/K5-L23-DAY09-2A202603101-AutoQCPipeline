"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    c = cfg["second_opinion"]
    conf_th = c["conf"]
    min_area_px = c["min_area_px"]
    fp_conf = c["fp_conf"]
    iou_missing = c["iou_missing"]
    iou_match = c["iou_match"]
    iou_loose = c["iou_loose"]
    issues = []
    for p in ds.image_files():
        stem = p.stem
        # Bỏ qua nếu không có dự đoán hoặc không có file nhãn
        if stem not in preds or not ds.label_path(stem).exists():
            continue
        im_size = ds.image_size(stem)
        if not im_size:
            continue
        W, H = im_size
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue
        # Đọc các nhãn hợp lệ kèm số dòng gốc
        valid_labels = []
        for line_num, text in raw_lines:
            try:
                b = parse_yolo_line(text)
                if 0 <= b[0] < len(ds.classes):
                    valid_labels.append((line_num, b[0], (b[1], b[2], b[3], b[4])))
            except ValueError:
                continue
        # Lọc các dự đoán tin cậy của model
        img_preds = preds.get(stem, [])
        P = [
            r
            for r in img_preds
            if r[1] >= conf_th and (r[4] * W * r[5] * H) >= min_area_px
        ]
        # A. Kiểm tra từng dự đoán trong P
        for r in P:
            r_cls = int(r[0])
            r_conf = float(r[1])
            r_box = (r[2], r[3], r[4], r[5])
            cands = []
            for line_num, l_cls, l_box in valid_labels:
                iou = iou_xywh(r_box, l_box)
                if iou >= iou_missing:
                    cands.append((l_cls, iou))
            if not cands:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model thấy vật {ds.classes[r_cls]} (conf {r_conf:.2f}), nhãn thiếu",
                        line=None,
                        extra={"conf": r_conf},
                    )
                )
            else:
                same_class = [cand for cand in cands if cand[0] == r_cls]
                if same_class:
                    best_same_iou = max(cand[1] for cand in same_class)
                    if best_same_iou < iou_loose:
                        issues.append(
                            Issue(
                                "second_opinion",
                                WARN,
                                "POSSIBLE_LOOSE_BOX",
                                stem,
                                f"box lỏng (IoU {best_same_iou:.2f} < {iou_loose})",
                                line=None,
                                extra={"conf": r_conf, "iou": best_same_iou},
                            )
                        )
                else:
                    diff_class = [cand for cand in cands if cand[0] != r_cls]
                    if diff_class:
                        best_diff_iou = max(cand[1] for cand in diff_class)
                        if best_diff_iou >= iou_match:
                            issues.append(
                                Issue(
                                    "second_opinion",
                                    WARN,
                                    "POSSIBLE_WRONG_CLASS",
                                    stem,
                                    f"model thấy {ds.classes[r_cls]} (conf {r_conf:.2f}), nhãn gán khác lớp",
                                    line=None,
                                    extra={"conf": r_conf, "iou": best_diff_iou},
                                )
                            )
        # B. Kiểm tra POSSIBLE_FALSE_POS trên từng nhãn hợp lệ
        fp_preds = [r for r in img_preds if r[1] >= fp_conf]
        for line_num, l_cls, l_box in valid_labels:
            has_match = any(
                iou_xywh(l_box, (r[2], r[3], r[4], r[5])) >= iou_missing
                for r in fp_preds
            )
            if not has_match:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"nhãn dòng {line_num} không khớp vật nào model thấy",
                        line=line_num,
                        extra={"conf": 0.0},
                    )
                )
    return issues