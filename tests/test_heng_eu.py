"""Eurocode 包扩充(EN1998 抗震 + EN1992 max配筋)：EU 从 1 条升为多条库 + 四方对照。

手算：
  EN1998 §4.4.3.2 损伤极限 drift_lim=0.005(脆性非结构)；drift=0.004 → 满足
  EN1998 §5.4.3.2.2 柱配筋率下限 0.01；rho=0.02 → 满足
  EN1992 §9.2.1.1(3) 最大配筋 rho_max=ndp_asmax=0.04；rho=0.02 → 满足
四方 story_drift(同一无量纲 drift)：CN 1/550=0.00182 < EU 0.005 = JP 0.005 < US 0.020。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.registry import get, rules_for
from heng.codes.rule import run_selftest, check
from heng.codes.jurisdiction import resolve
from heng.dualcode import dual_code_report


EU_NEW = ["EU.EN1998-1.4.4.3.2", "EU.EN1998-1.5.4.3.2.2", "EU.EN1992-1-1.9.2.1.1max"]


def test_eu_new_rules_selftest():
    for rid in EU_NEW:
        ok, msg = run_selftest(get(rid))
        assert ok, f"{rid} CI 失败: {msg}"


def test_eu_library_grew():
    eu = rules_for("EU")
    assert len(eu) >= 4, f"EU 应已多条(got {len(eu)})"
    concepts = {r.concept for r in eu}
    assert {"story_drift", "column_min_longitudinal", "max_flexural_reinforcement"} <= concepts


def test_four_way_story_drift_order():
    """四辖区 story_drift 限值排序：CN < EU = JP < US。"""
    ctx = {"element": "story", "system": "frame", "drift": 0.004}
    lim = {}
    for jur in ("CN", "EU", "JP", "US"):
        r = [x for x in rules_for(jur) if x.concept == "story_drift"][0]
        env = dict(ctx)
        res = check(r, env)
        # 取限值中间量
        lk = [k for k in res.values if k.endswith(("_lim",))][0]
        lim[jur] = res.values[lk]
    assert lim["CN"] < lim["EU"], lim
    assert abs(lim["EU"] - lim["JP"]) < 1e-9, lim
    assert lim["JP"] < lim["US"], lim


def test_eu_max_reinforcement_needs_ndp():
    """max 配筋规则用 NDP 参数(ndp_asmax)——resolve('EU').ndp 提供后可校核。"""
    r = get("EU.EN1992-1-1.9.2.1.1max")
    ctx = dict({"element": "beam", "material": "reinforced_concrete", "rho": 0.02},
               **resolve("EU").ndp)
    assert check(r, ctx).ok is True
    ctx2 = dict(ctx, rho=0.05)      # 超 0.04
    assert check(r, ctx2).ok is False


def test_cn_eu_drift_dualcode():
    rep = dual_code_report({"element": "story", "system": "frame", "drift": 0.004}, "CN", "EU")
    row = [r for r in rep["rows"] if r["concept"] == "story_drift"][0]
    assert row["a"]["limit"] < row["b"]["limit"] and "CN" in row["note"] and "更严" in row["note"]


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
