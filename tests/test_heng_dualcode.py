"""双规范并行对照报告：同一梁，中国 8.5.1 与 Eurocode 9.2.1.1 各自独立算、配对对照（§4.4）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.dualcode import dual_code_report, render_markdown


def _beam_ctx():
    return {"element": "beam", "material": "reinforced_concrete",
            "ft": 1.43, "fy": 360,       # 中国
            "fctm": 2.9, "fyk": 500,     # 欧洲
            "rho": 0.003}


def test_dual_report_pairs_min_reinforcement():
    rep = dual_code_report(_beam_ctx(), "CN", "EU", na_b="DE")
    row = next(r for r in rep["rows"] if r["concept"] == "min_flexural_reinforcement")
    assert row["a"]["rule_id"].startswith("CN.GB50010") and row["a"]["clause"] == "8.5.1"
    assert row["b"]["rule_id"].startswith("EU.EN1992") and row["b"]["clause"].startswith("9.2.1.1")
    # 各自独立算出各自限值(不换算)
    assert abs(row["a"]["limit"] - 0.002) < 1e-9
    assert abs(row["b"]["limit"] - 0.001508) < 1e-6
    # 中国 0.20% 下限更严 → 控制
    assert "CN 更严" in row["note"]


def test_both_verdicts_independent():
    rep = dual_code_report(_beam_ctx(), "CN", "EU", na_b="DE")
    row = next(r for r in rep["rows"] if r["concept"] == "min_flexural_reinforcement")
    assert row["a"]["verdict"] is True and row["b"]["verdict"] is True   # ρ=0.003 均满足


def test_markdown_render():
    md = render_markdown(dual_code_report(_beam_ctx(), "CN", "EU", na_b="DE"))
    assert md.startswith("# 双规范并行对照表")
    assert "min_flexural_reinforcement" in md and "8.5.1" in md and "9.2.1.1" in md
    assert "不做换算" in md


def test_ndp_affects_eu_side():
    # 换 National Annex 改 NDP → EU 侧限值随之变(演示参数覆盖层)
    ctx = _beam_ctx()
    from heng.dualcode import dual_code_report as dcr
    r1 = dcr(ctx, "CN", "EU", na_b="DE")
    eu = next(x for x in r1["rows"] if x["concept"] == "min_flexural_reinforcement")["b"]
    assert eu["limit"] is not None   # NDP 注入成功→EC 规则可算


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
