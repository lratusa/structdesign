"""规范库 CI（设计书 §4.1）：每条 Rule 必须通过其自带的官方算例/手算基准。

这是「衡」规范引擎的核心质量门：任何条文更新必须通过全部回归测试才能发布。
同时验证：强条红线、失败判定、多辖区。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.registry import all_rules, rules_for, scan
from heng.codes.rule import run_selftest, check


def test_every_rule_has_and_passes_its_testcase():
    rules = all_rules()
    assert len(rules) >= 6, len(rules)
    for r in rules:
        assert r.test.get("inputs"), f"{r.rule_id} 缺测试用例(违反规范库CI要求)"
        okk, msg = run_selftest(r)
        assert okk, f"{r.rule_id} CI 失败: {msg}"


def test_rule_id_format():
    for r in all_rules():
        parts = r.rule_id.split(".")
        assert len(parts) >= 3, r.rule_id           # 辖区.规范-版本.条号
        assert r.jurisdiction in ("CN", "EU", "JP", "US")


def test_axial_ratio_fails_when_over():
    from heng.codes.registry import get
    r = get("CN.GB50011-2010(2016).6.3.6")
    res = check(r, {"element": "column", "material": "reinforced_concrete", "grade": "二级", "mu": 0.95})
    assert res.applicable and res.ok is False and res.values["mu_lim"] == 0.75


def test_provenance_present():
    from heng.codes.registry import get
    r = get("CN.GB50010-2010(2015).8.5.1")
    res = check(r, {"element": "beam", "material": "reinforced_concrete", "ft": 1.43, "fy": 360, "rho": 0.001})
    assert res.ok is False
    assert res.provenance.get("clause") == "8.5.1" and res.mandatory is True   # 强条溯源


def test_mandatory_redline_scan():
    # 剪重比强条不满足 → 红线
    ctx = {"element": "structure", "intensity": "8", "shear_weight": 0.010,   # <0.032 不满足
           "period_ratio": 0.85, "disp_ratio": 1.1}
    s = scan(ctx, "CN")
    assert s["mandatory_failed"] >= 1 and s["red_line"] is True


def test_scan_all_pass_no_redline():
    ctx = {"element": "structure", "intensity": "8", "shear_weight": 0.035,
           "period_ratio": 0.85, "disp_ratio": 1.1}
    s = scan(ctx, "CN")
    assert s["failed"] == 0 and s["red_line"] is False and s["total"] >= 3


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
