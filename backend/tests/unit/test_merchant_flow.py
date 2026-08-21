from __future__ import annotations

from pathlib import Path
import pytest


def test_no_legacy_routing_symbols_in_runtime_source():
    backend_root = Path(__file__).resolve().parents[2]
    forbidden_symbols = (
        "InputPreparationService",
        "decide_route(",
        "query_decision(",
        "NativeMerchantAdvisorCrew",
        "merchant_execution_mode",
    )
    for py_file in backend_root.rglob("*.py"):
        rel_str = str(py_file.relative_to(backend_root))
        if rel_str.startswith("tests/") or rel_str.startswith("evals/") or "alembic" in rel_str or ".venv" in rel_str:
            continue
        content = py_file.read_text(encoding="utf-8")
        for forbidden in forbidden_symbols:
            assert forbidden not in content, f"Found forbidden '{forbidden}' in {rel_str}"


def test_filter_mentioned_merchants_matches_name_and_ref():
    from flows.merchant_flow import _filter_mentioned_merchants

    all_merchants = [
        {"merchant_id": "1", "name": "Cơm Tấm Ba Ghiền - Đặng Văn Ngữ", "merchant_ref": "pub_01"},
        {"merchant_id": "2", "name": "Phở Hòa Pasteur", "merchant_ref": "pub_02"},
        {"merchant_id": "3", "name": "Bún Chả Hà Nội", "merchant_ref": "pub_03"},
    ]

    # Matching main brand name without branch
    res1 = _filter_mentioned_merchants(all_merchants, "Bạn nên tham khảo thực đơn của quán Cơm Tấm Ba Ghiền nhé.")
    assert len(res1) == 1
    assert res1[0]["merchant_id"] == "1"

    # Matching ref
    res2 = _filter_mentioned_merchants(all_merchants, "Xem chi tiết tại pub_02")
    assert len(res2) == 1
    assert res2[0]["merchant_id"] == "2"

    # Fallback to top if no specific mention
    res3 = _filter_mentioned_merchants(all_merchants, "Không có tên quán nào.")
    assert len(res3) == 3

