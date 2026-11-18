"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # Chuyển image_stems và reviewed về dạng set để tìm kiếm nhanh O(1)
    image_stems_set = set(image_stems)
    reviewed_set = set(reviewed) if reviewed else set()
    # 1. Đếm tổng số lỗi bắt buộc (ERROR)
    n_errors = sum(1 for i in issues if i.severity == ERROR)
    # 2. Tìm tập hợp các ẢNH có cảnh báo (WARN) hợp lệ và chưa được người duyệt
    warn_images = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in image_stems_set and i.image not in reviewed_set
    }
    n_warn_images = len(warn_images)
    n_images = len(image_stems)
    # 3. Tính tỉ lệ cảnh báo (chú ý tránh chia cho 0 khi n_images == 0)
    warn_ratio = round(n_warn_images / n_images, 4) if n_images > 0 else 0.0
    threshold = cfg["gate"]["warn_ratio_hold"]
    reasons = []
    # 4. Ra quyết định theo cây quyết định
    if n_errors > 0:
        decision = "Rework"
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (ERROR)")
    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons.append(
            f"Tỉ lệ ảnh có cảnh báo {warn_ratio:.2%} ({n_warn_images}/{n_images} ảnh) >= ngưỡng cho phép {threshold:.2%}"
        )
    else:
        decision = "Release"
        reasons.append(
            f"Không còn lỗi bắt buộc và tỉ lệ cảnh báo {warn_ratio:.2%} ({n_warn_images}/{n_images} ảnh) dưới ngưỡng {threshold:.2%}"
        )
    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
