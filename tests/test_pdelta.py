"""
P-Δ / 屈曲验证 —— 欧拉临界荷载解析解。

铰接-铰接柱: Pcr = π²EI/L²
悬臂柱(固定-自由): Pcr = π²EI/(2L)²
二阶效应: 轴压下侧移与弯矩被放大 ~1/(1-P/Pcr)
"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame2d import FrameModel, Node, Member, NodalLoad
from structdesign.analysis.pdelta import buckling_factor, second_order_solve


def approx(a, b, tol=5e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def _column(n_elem, restraint_top, restraint_bot, P0=1000.0, L=4000.0,
            E=2e5, I=8.333e6, A=1e4):
    m = FrameModel()
    ys = [L * i / n_elem for i in range(n_elem + 1)]
    for i, y in enumerate(ys):
        if i == 0:
            r = restraint_bot
        elif i == n_elem:
            r = restraint_top
        else:
            r = (False, False, False)
        m.add_node(Node(str(i), 0.0, y, r))
    for i in range(n_elem):
        m.add_member(Member(f"e{i}", str(i), str(i + 1), E, A, I))
    m.add_load(NodalLoad(str(n_elem), Fy=-P0))   # 顶部轴压 P0
    return m, E, I, L, P0


def test_pinned_pinned_buckling():
    # 两端铰接：底(ux,uy固定,rz自由)、顶(uy自由加载,ux自由,rz自由)→需顶ux受约束才侧屈
    # 经典铰接柱：两端横向受约束(ux)、可转动(rz自由)
    m, E, I, L, P0 = _column(6,
                             restraint_top=(True, False, False),   # 顶 ux 约束, uy 自由(加载), rz 自由
                             restraint_bot=(True, True, False))     # 底 铰接
    lam = buckling_factor(m)
    Pcr = lam * P0
    Pe = math.pi ** 2 * E * I / L ** 2
    assert approx(Pcr, Pe, 5e-2), (Pcr, Pe)


def test_cantilever_buckling():
    # 悬臂：底固定，顶自由
    m, E, I, L, P0 = _column(6,
                             restraint_top=(False, False, False),
                             restraint_bot=(True, True, True))
    lam = buckling_factor(m)
    Pcr = lam * P0
    Pe = math.pi ** 2 * E * I / (2 * L) ** 2
    assert approx(Pcr, Pe, 6e-2), (Pcr, Pe)


def test_second_order_amplifies():
    # 悬臂柱：顶部水平力 + 轴压，二阶弯矩应大于一阶
    from structdesign.analysis.frame2d import solve
    m, E, I, L, P0 = _column(4,
                             restraint_top=(False, False, False),
                             restraint_bot=(True, True, True), P0=2e5)
    m.add_load(NodalLoad("4", Fx=5000.0))   # 顶部水平力
    r1 = solve(m)["e0"]
    r2 = second_order_solve(m)["e0"]
    assert abs(r2.Mi) > abs(r1.Mi) * 1.02, (r1.Mi, r2.Mi)


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
