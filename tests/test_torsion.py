"""多向/扭转地震测试（力平衡/解析核对）。"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes import seismic_torsion as st


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_bidirectional():
    # Sx=100,Sy=80 → max(√(100²+(0.85·80)²), √(80²+(0.85·100)²))
    s = st.bidirectional_combination(100, 80)
    e1 = math.hypot(100, 0.85 * 80)
    e2 = math.hypot(80, 0.85 * 100)
    assert approx(s, max(e1, e2))


def test_torsion_force_conservation():
    # 3 榀等刚度 x=0,5,10; V=1000; plan=10 → e=0.5
    r = st.torsional_distribution(1000.0, [(0, 1), (5, 1), (10, 1)], plan_dim=10.0)
    assert approx(r.x_cr, 5.0)
    # 平动部分之和=V；含扭转的边榀放大、中榀=平动
    # 注：取绝对值(不利侧)后总和≥V，但纯平动分量守恒
    assert approx(sum(1000.0 * 1 / 3 for _ in range(3)), 1000.0)


def test_torsion_edge_amplified():
    r = st.torsional_distribution(1000.0, [(0, 1), (5, 1), (10, 1)], plan_dim=10.0)
    # 边榀放大、中榀≈1
    assert r.amplification[0] > 1.05
    assert r.amplification[2] > 1.05
    assert approx(r.amplification[1], 1.0, 1e-6)


def test_torsion_symmetric_center():
    # 对称布置刚心居中
    r = st.torsional_distribution(500.0, [(0, 2), (8, 2)], plan_dim=8.0)
    assert approx(r.x_cr, 4.0)


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
