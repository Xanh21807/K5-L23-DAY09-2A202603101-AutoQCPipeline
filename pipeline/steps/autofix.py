"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401
from pathlib import Path

def fix(ds, issues, cfg):
    # Chỉ xử lý các lỗi bắt buộc ERROR
    error_issues = [i for i in issues if i.severity == ERROR]
    if not error_issues:
        return []
    fixes = []
    removed_images = set()
    # 1. BAD_CLASS_NAME: sửa trường 'names' trong data.yaml
    for i in error_issues:
        if i.code == "BAD_CLASS_NAME" and ds.yaml_path.exists():
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            before = str(data.get("names", ""))
            data["names"] = list(cfg["classes"])
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            fixes.append({
                "image": "data.yaml",
                "line": "",
                "action": "rename_classes",
                "before": before,
                "after": str(cfg["classes"]),
            })
    # 2. Xóa ảnh + nhãn: DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE
    remove_codes = {
        "DUP_IMAGE_EXACT",
        "DUP_IMAGE_NEAR",
        "LEAK_TEST",
        "CORRUPT_IMAGE",
        "BAD_SIZE",
    }
    for i in error_issues:
        if i.code in remove_codes and i.image not in removed_images:
            removed_images.add(i.image)
            img_p = ds.image_path(i.image)
            if img_p and img_p.exists():
                img_p.unlink()
            lbl_p = ds.label_path(i.image)
            if lbl_p.exists():
                lbl_p.unlink()
            fixes.append({
                "image": i.image,
                "line": "",
                "action": "remove_image",
                "before": i.code,
                "after": "đã xoá ảnh và nhãn",
            })
    # 3. MISSING_LABEL_FILE: ghi nhận chuyển người gán (không tạo file rỗng)
    for i in error_issues:
        if i.code == "MISSING_LABEL_FILE":
            fixes.append({
                "image": i.image,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })
    # 4. Gom các lỗi dòng theo ảnh và theo số dòng gốc
    # line_issues[stem][line_num] = list of issues
    line_issues = defaultdict(lambda: defaultdict(list))
    for i in error_issues:
        if (
            i.image not in removed_images
            and i.line is not None
            and i.code in {
                "BAD_FORMAT",
                "BAD_CLASS_ID",
                "BOX_ZERO",
                "DUP_BOX",
                "BOX_OUT_OF_IMAGE",
            }
        ):
            line_issues[i.image][i.line].append(i)
    # 5. Duyệt và ghi đè từng file nhãn có lỗi dòng
    for stem in sorted(line_issues.keys()):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        file_issues = line_issues[stem]
        new_lines = []
        for line_num, orig_text in enumerate(raw_lines, 1):
            if line_num not in file_issues:
                new_lines.append(orig_text)
                continue
            codes = {iss.code for iss in file_issues[line_num]}
            # Nếu dính lỗi format / class / zero / dup -> xoá dòng thắng
            if codes & {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}:
                fixes.append({
                    "image": stem,
                    "line": line_num,
                    "action": "drop_line",
                    "before": orig_text,
                    "after": "(đã xoá)",
                })
                continue
            # Nếu chỉ dính BOX_OUT_OF_IMAGE -> thử cắt box về [0, 1]
            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    c_id, cx, cy, w, h = parse_yolo_line(orig_text)
                    x1 = max(0.0, min(1.0, cx - w / 2))
                    y1 = max(0.0, min(1.0, cy - h / 2))
                    x2 = max(0.0, min(1.0, cx + w / 2))
                    y2 = max(0.0, min(1.0, cy + h / 2))
                    new_w = x2 - x1
                    new_h = y2 - y1
                    # Box nằm hẳn ngoài ảnh -> xoá dòng
                    if new_w <= 0 or new_h <= 0:
                        fixes.append({
                            "image": stem,
                            "line": line_num,
                            "action": "drop_line",
                            "before": orig_text,
                            "after": "(đã xoá: box ngoài ảnh)",
                        })
                        continue
                    new_cx = (x1 + x2) / 2
                    new_cy = (y1 + y2) / 2
                    new_text = f"{c_id} {new_cx:.6f} {new_cy:.6f} {new_w:.6f} {new_h:.6f}"
                    new_lines.append(new_text)
                    fixes.append({
                        "image": stem,
                        "line": line_num,
                        "action": "clip_box",
                        "before": orig_text,
                        "after": new_text,
                    })
                except ValueError:
                    fixes.append({
                        "image": stem,
                        "line": line_num,
                        "action": "drop_line",
                        "before": orig_text,
                        "after": "(đã xoá: lỗi parse)",
                    })
                    continue
        # Ghi lại file nhãn một lần duy nhất
        lp.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    return fixes