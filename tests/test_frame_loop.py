"""
真实外层闭环测试：截面生长 + 重分析 + 收敛。

验证：(1) 超限框架能在建筑可行域内收敛；(2) 收敛后柱轴压比满足；
     (3) 迭代过程中内力发生重分布（梁弯矩随柱截面变化而改变）。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame2d import NodalLoad
from structdesign.design_frame import SecBox, FrameSpec, closed_loop_design


def _spec():
    H, Lb = 3600.0, 7000.0
    cL = SecBox(350, 350, "C40", "column", h_max=900, seismic_grade="二级")
    cR = SecBox(350, 350, "C40", "column", h_max=900, seismic_grade="二级")
    bm = SecBox(300, 500, "C30", "beam", h_max=1000, seismic_grade="二级")
    return FrameSpec(
        nodes={"1": (0, 0, (True, True, True)), "2": (0, H, (False,)*3),
               "3": (Lb, H, (False,)*3), "4": (Lb, 0, (True, True, True))},
        members={"C1": ("1", "2", cL, 0.0), "B1": ("2", "3", bm, 45.0),
                 "C2": ("4", "3", cR, 0.0)},
        loads=[NodalLoad("2", Fx=120000, Fy=-2600000), NodalLoad("3", Fy=-2600000)])


def test_loop_converges_and_satisfies():
    res = closed_loop_design(_spec(), h_step=50.0)
    assert res.converged, res.history
    assert res.iterations >= 2
    # 收敛后两根柱轴压比均满足
    assert "✔" in res.final_forces["C1"], res.final_forces["C1"]
    assert "✔" in res.final_forces["C2"], res.final_forces["C2"]


def test_force_redistribution():
    """柱从初始到生长后，梁弯矩应改变（刚度变→内力重分布）。"""
    from structdesign.design_frame import _build
    from structdesign.analysis.frame2d import solve
    spec = _spec()
    M0 = abs(solve(_build(spec))["B1"].M_mid)
    res = closed_loop_design(spec, h_step=50.0)  # 会改变 spec 中截面
    M1 = abs(solve(_build(spec))["B1"].M_mid)
    assert abs(M1 - M0) > 1e6, (M0, M1)  # 弯矩变化 >1 kN·m


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
