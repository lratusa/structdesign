"""美国规范 seed(ACI 318-19 / ASCE 7-22)：US 从"辖区可解析"升为"有条文库"。

手算：
  ACI §9.6.1.2 rho_min=max(3√4000/60000, 200/60000)=max(0.003162,0.003333)=0.003333；rho=0.005 → 满足
  ACI §10.6.1.1 柱配筋率下限 0.01；rho=0.02 → 满足
  ASCE 7 §12.12.1 drift_lim=0.020；drift=0.01 → 满足
三方 story_drift 对照(同一无量纲 drift)：CN 1/550=0.00182 < JP 0.005 < US 0.020 → 中国最严。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.registry import get, rules_for
from heng.codes.rule import run_selftest
from heng.dualcode import dual_code_report


US_IDS = ["US.ACI318-19.9.6.1.2", "US.ACI318-19.10.6.1.1", "US.ASCE7-22.12.12.1"]


def test_us_rules_selftest():
    for rid in US_IDS:
        ok, msg = run_selftest(get(rid))
        assert ok, f"{rid} CI 失败: {msg}"


def test_us_now_has_code_library():
    us = rules_for("US")
    assert len(us) >= 3, "US 应已有条文库"
    assert all(r.jurisdiction == "US" for r in us)


def test_three_way_story_drift_strictness():
    """CN/JP/US 层间位移角三方对照：中国最严(限值最小)。"""
    ctx = {"element": "story", "system": "frame", "drift": 0.004}
    # CN vs US
    cn_us = dual_code_report(ctx, "CN", "US")
    row = [r for r in cn_us["rows"] if r["concept"] == "story_drift"][0]
    assert row["a"]["limit"] < row["b"]["limit"], "CN 限值应小于 US"
    assert "CN" in row["note"] and "更严" in row["note"]
    # JP vs US：JP(0.005) 严于 US(0.020)
    jp_us = dual_code_report(ctx, "JP", "US")
    r2 = [r for r in jp_us["rows"] if r["concept"] == "story_drift"][0]
    assert r2["a"]["limit"] < r2["b"]["limit"], "JP 限值应小于 US"


def test_us_drift_pass_fail_matches_limit():
    r = get("US.ASCE7-22.12.12.1")
    from heng.codes.rule import check
    assert check(r, {"element": "story", "drift": 0.015}).ok is True    # <0.02
    assert check(r, {"element": "story", "drift": 0.025}).ok is False   # >0.02


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
