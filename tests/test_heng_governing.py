"""控制条文标注(设计书 §6.2)：找出"卡住构件"的那条规范(紧迫度最高)。

手算：一根柱 element=column,material=rc,grade=一级。适用条文含
  6.3.7 柱最小配筋率(下限 rho>=0.009) 与 6.3.6 轴压比(上限 mu<=mu_lim)。
造两种上下文，验证控制条文正确切换：
  ① rho 恰略高于 0.009、轴压比很低 → 6.3.7 紧迫度≈1 最高 → 控制条文=最小配筋率。
  ② rho 充裕、轴压比接近限值 → 6.3.6 紧迫度最高 → 控制条文=轴压比。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.governing import governing_clause, annotate


def _col(**kw):
    base = {"element": "column", "material": "reinforced_concrete", "grade": "一级"}
    base.update(kw)
    return base


def test_min_reinforcement_governs():
    # rho 贴着下限 0.009，轴压比很小(0.2) → 最小配筋率最紧迫
    ctx = _col(rho=0.0091, mu=0.20, axial_ratio=0.20)
    g = governing_clause(ctx)["governing"]
    assert g is not None
    assert "6.3.7" in g["rule_id"] or "配筋" in g["title"], g


def test_axial_ratio_governs():
    # rho 充裕(0.02)，轴压比接近一级限值(0.65) → 轴压比最紧迫
    ctx = _col(rho=0.02, mu=0.64, axial_ratio=0.64)
    g = governing_clause(ctx)["governing"]
    assert g is not None
    assert "6.3.6" in g["rule_id"] or "轴压比" in g["title"], g


def test_criticality_at_boundary_is_one():
    """恰在下限：demand=capacity → 紧迫度≈1。"""
    ctx = _col(rho=0.009, mu=0.2, axial_ratio=0.2)
    ranked = governing_clause(ctx)["ranked"]
    minr = [x for x in ranked if "6.3.7" in x["rule_id"]][0]
    assert abs(minr["criticality"] - 1.0) < 1e-3, minr


def test_annotate_text():
    ctx = _col(rho=0.0091, mu=0.20, axial_ratio=0.20)
    s = annotate(ctx)
    assert "控制条文" in s


def test_ranked_sorted_desc():
    ctx = _col(rho=0.012, mu=0.5, axial_ratio=0.5)
    ranked = governing_clause(ctx)["ranked"]
    crits = [x["criticality"] for x in ranked]
    assert crits == sorted(crits, reverse=True) and len(ranked) >= 2


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
