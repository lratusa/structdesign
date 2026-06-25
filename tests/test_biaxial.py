"""柱双向偏压 + 3D 杆端内力测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes.gb50010_column import design_column_biaxial, design_column_symmetric
from structdesign.analysis.frame3d import Frame3D, Node3D, Member3D, Load3D, member_forces


def approx(a, b, tol=1e-3):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_reduces_to_uniaxial_when_My_zero():
    # My=0 → 双偏压退化为单偏压(绕x)
    r = design_column_biaxial(600, 600, 3000, 400, 0, "C40", "HRB400")
    uni = design_column_symmetric(600, 600, 3000, 400, "C40", "HRB400")
    assert approx(r.As_total, uni.As_total, 1e-6), (r.As_total, uni.As_total)


def test_biaxial_more_than_uniaxial():
    # 弯矩控制工况(轴力较小)：双向都有弯矩 → 用钢多于单向
    uni = design_column_biaxial(600, 600, 1000, 500, 0, "C40", "HRB400")
    bi = design_column_biaxial(600, 600, 1000, 500, 400, "C40", "HRB400")
    assert bi.As_total > uni.As_total, (uni.As_total, bi.As_total)


def test_symmetric_biaxial_equal_contrib():
    r = design_column_biaxial(600, 600, 3000, 350, 350, "C40", "HRB400")
    assert approx(r.As_x, r.As_y, 1e-6)
    assert approx(r.As_total, 2 * r.As_x - r.As0, 1e-6)


def test_3d_member_axial():
    # 竖向柱顶部竖向力 → 轴力≈力(数值)
    m = Frame3D()
    m.add_node(Node3D("1", 0, 0, 0, (True,)*6))
    m.add_node(Node3D("2", 0, 0, 3600, (False,)*6))
    m.add_member(Member3D("c", "1", "2", 3e4, 1.3e4, 4e5, 1e10, 1e10, 1e10))
    m.add_load(Load3D("2", fz=-1e6))
    f = member_forces(m)["c"]
    assert approx(abs(f["N"]), 1e6, 1e-3), f["N"]


def test_3d_member_biaxial_moments():
    # 顶部 X 与 Y 水平力 → 两方向弯矩均非零
    m = Frame3D()
    m.add_node(Node3D("1", 0, 0, 0, (True,)*6))
    m.add_node(Node3D("2", 0, 0, 3600, (False,)*6))
    m.add_member(Member3D("c", "1", "2", 3e4, 1.3e4, 4e5, 1e10, 1e10, 1e10))
    m.add_load(Load3D("2", fx=5e4, fy=5e4))
    f = member_forces(m)["c"]
    assert f["My"] > 0 and f["Mz"] > 0


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
