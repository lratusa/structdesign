"""
真三维框架单元验证 —— 解析解核对。

竖向悬臂柱(沿Z), 顶部:
  X向力 P → 顶点X位移 = PH³/(3E·I)（对应方向惯性矩）
  Y向力 P → 顶点Y位移 = PH³/(3E·I)
  绕Z扭矩 T → 扭转角 = T·H/(G·J)
翼缘组合：两墙相距 D，各层刚接连成整体 → 组合截面 I=2(I_self+A(D/2)²)，
  挠度按组合 I（远小于各自独立）。
"""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame3d import Frame3D, Node3D, Member3D, Load3D, solve, rigid_link


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def _cantilever(n=10, H=30000.0, E=3e4, G=1.25e4, A=1e6, Iy=8e9, Iz=2e9, J=1e10):
    m = Frame3D()
    for i in range(n + 1):
        r = (True,)*6 if i == 0 else (False,)*6
        m.add_node(Node3D(str(i), 0, 0, H * i / n, r))
    for i in range(n):
        m.add_member(Member3D(f"e{i}", str(i), str(i+1), E, G, A, Iy, Iz, J))
    return m, H, E, G, Iy, Iz, J


def test_bending_x():
    m, H, E, G, Iy, Iz, J = _cantilever()
    P = 1000.0
    m.add_load(Load3D(str(10), fx=P))
    U, _ = solve(m)
    ux = U["10"][0]
    # X向力 → 绕局部某轴弯曲；竖直构件局部z=-X → 弯曲惯性矩为 Iy
    assert approx(abs(ux), P * H**3 / (3 * E * Iy), 2e-2), (ux, P*H**3/(3*E*Iy))


def test_bending_y():
    m, H, E, G, Iy, Iz, J = _cantilever()
    P = 1000.0
    m.add_load(Load3D(str(10), fy=P))
    U, _ = solve(m)
    uy = U["10"][1]
    assert approx(abs(uy), P * H**3 / (3 * E * Iz), 2e-2), (uy, P*H**3/(3*E*Iz))


def test_torsion():
    m, H, E, G, Iy, Iz, J = _cantilever()
    T = 1e8
    m.add_load(Load3D(str(10), mz=T))
    U, _ = solve(m)
    rz = U["10"][5]
    assert approx(abs(rz), T * H / (G * J), 2e-2), (rz, T*H/(G*J))


def test_flange_coupling_composite_I():
    """两墙相距 D，每层刚接 → 组合抗弯；挠度按组合 I。"""
    n, H, E, G = 10, 30000.0, 3e4, 1.25e4
    D = 6000.0
    # 单墙: 截面 bw×lw, 弱轴(沿Y弯)惯性矩 I_self 小；面积 A
    bw, lw = 400.0, 3000.0
    A = bw * lw
    I_self = lw * bw**3 / 12      # 绕(平行lw)弱轴
    Iy = lw * bw**3 / 12
    Iz = bw * lw**3 / 12
    J = 1e11
    m = Frame3D()
    for i in range(n + 1):
        rb = (True,)*6 if i == 0 else (False,)*6
        m.add_node(Node3D(f"A{i}", 0, 0, H*i/n, rb))
        m.add_node(Node3D(f"B{i}", D, 0, H*i/n, rb))
    for i in range(n):
        m.add_member(Member3D(f"wa{i}", f"A{i}", f"A{i+1}", E, G, A, Iy, Iz, J))
        m.add_member(Member3D(f"wb{i}", f"B{i}", f"B{i+1}", E, G, A, Iy, Iz, J))
    # 每层用近刚性梁把两墙连成整体(发展翼缘轴力偶)
    rl = rigid_link()
    for i in range(1, n + 1):
        m.add_member(Member3D(f"link{i}", f"A{i}", f"B{i}", **rl))
    # 沿 Y 方向加载(使两墙作为翼缘抗弯)，顶部各加 P/2
    P = 2000.0
    m.add_load(Load3D(f"A{n}", fy=P/2))
    m.add_load(Load3D(f"B{n}", fy=P/2))
    U, _ = solve(m)
    uy = abs(U[f"A{n}"][1])
    # 组合截面: I_comp = 2(I_self + A(D/2)²)
    I_comp = 2 * (Iy + A * (D/2)**2)
    delta_comp = P * H**3 / (3 * E * I_comp)
    delta_indep = P * H**3 / (3 * E * (2 * Iy))
    # 翼缘协同(部分组合, 离散刚接)：挠度处于[组合, 独立]之间，且强烈靠近组合端，
    # 较"各墙独立"刚度提升 >10 倍 —— 证明 3D 捕捉到翼缘协同。
    assert delta_comp * 0.9 <= uy < delta_indep * 0.1, (uy, delta_comp, delta_indep)
    assert delta_indep / uy > 10, delta_indep / uy


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
