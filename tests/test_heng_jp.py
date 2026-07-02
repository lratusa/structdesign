"""日本包 seed：施行令强制条文入引擎 + 中日双规范并行(层间变形角 1/550 vs 1/200)。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.registry import get
from heng.codes.rule import check, run_selftest
from heng.codes.jurisdiction import resolve
from heng.dualcode import dual_code_report


def test_jp_rules_ci():
    for rid in ("JP.建築基準法施行令.77", "JP.建築基準法施行令.82の2"):
        okk, msg = run_selftest(get(rid)); assert okk, f"{rid}: {msg}"


def test_jp_column_min_longitudinal():
    r = get("JP.建築基準法施行令.77")
    assert check(r, {"element": "column", "material": "reinforced_concrete", "rho": 0.010}).ok is True
    assert check(r, {"element": "column", "material": "reinforced_concrete", "rho": 0.005}).ok is False
    assert r.mandatory                                        # 强制


def test_jp_drift_limit():
    r = get("JP.建築基準法施行令.82の2")
    assert check(r, {"element": "story", "drift": 0.003}).ok is True      # 1/333 ≤ 1/200
    assert check(r, {"element": "story", "drift": 0.006}).ok is False     # 1/167 > 1/200


def test_jp_jurisdiction():
    cs = resolve("JP", "building")
    assert cs.jurisdiction == "JP" and "確認申請" in cs.review_process


def test_cn_jp_dual_drift_divergence():
    """同一 0.003 的层间位移角：中国 1/550 超限✗，日本 1/200 满足✔ —— 跨国差异对照。"""
    ctx = {"element": "story", "system": "frame", "drift": 0.003}
    rep = dual_code_report(ctx, "CN", "JP")
    row = next(r for r in rep["rows"] if r["concept"] == "story_drift")
    assert row["a"]["clause"] == "5.5.1" and row["a"]["verdict"] is False   # 中国超限
    assert row["b"]["clause"] == "第82条の2" and row["b"]["verdict"] is True  # 日本满足
    assert "限值不同" in row["note"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
