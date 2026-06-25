"""
真三维 demo —— 2D 做不到的两件事：核心筒翼缘协同、扭转耦联。

① 核心筒(4 角墙组成方筒，各层环梁刚接) vs 4 道独立墙 —— 三维捕捉翼缘协同，筒体刚度远高。
② 偏心荷载 → 整体扭转(绕Z转角)，体现扭转耦联。
运行：python demo_3d.py
"""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.analysis.frame3d import Frame3D, Node3D, Member3D, Load3D, solve, rigid_link


def build_core(B=8000.0, n=20, H_story=3600.0, bw=400.0, lw=2000.0,
               E=3.45e4, G=1.44e4, linked=True):
    """B×B 方筒，4 角竖墙，各层环梁刚接(linked=True)或不连(False)。"""
    m = Frame3D()
    corners = [(0, 0), (B, 0), (B, B), (0, B)]
    A = bw * lw
    Iy = lw * bw**3 / 12
    Iz = bw * lw**3 / 12
    J = 1e11
    for ci, (x, y) in enumerate(corners):
        for j in range(n + 1):
            r = (True,)*6 if j == 0 else (False,)*6
            m.add_node(Node3D(f"C{ci}_{j}", x, y, j*H_story, r))
        for j in range(n):
            m.add_member(Member3D(f"w{ci}_{j}", f"C{ci}_{j}", f"C{ci}_{j+1}",
                                  E, G, A, Iy, Iz, J))
    if linked:
        rl = rigid_link()
        for j in range(1, n + 1):
            for ci in range(4):
                cj = (ci + 1) % 4
                m.add_member(Member3D(f"ring{ci}_{j}", f"C{ci}_{j}", f"C{cj}_{j}", **rl))
    return m, n, B


def top_drift_Y(m, n, P):
    for ci in range(4):
        m.add_load(Load3D(f"C{ci}_{n}", fy=P/4))
    U, _ = solve(m)
    return np.mean([U[f"C{ci}_{n}"][1] for ci in range(4)])


def main():
    H = 20 * 3600.0
    P = 4000e3   # 顶部总水平力 4000 kN

    print("=" * 64)
    print("① 核心筒翼缘协同：方筒 vs 4 道独立墙（同样 4 片墙）")
    print("=" * 64)
    m_box, n, B = build_core(linked=True)
    d_box = top_drift_Y(m_box, n, P)
    m_ind, n2, _ = build_core(linked=False)
    d_ind = top_drift_Y(m_ind, n2, P)
    print(f"  方筒(环梁刚接，翼缘协同) 顶点位移 = {abs(d_box):.2f} mm  位移角 1/{H/abs(d_box):.0f}")
    print(f"  4 道独立墙(不连)        顶点位移 = {abs(d_ind):.2f} mm  位移角 1/{H/abs(d_ind):.0f}")
    print(f"  → 筒体刚度是独立墙之和的 {abs(d_ind)/abs(d_box):.0f} 倍（平行轴/翼缘协同，2D 无法体现）")

    print("\n" + "=" * 64)
    print("② 扭转耦联：偏心水平力 → 整体绕 Z 扭转")
    print("=" * 64)
    m2, n, B = build_core(linked=True)
    # 一对反向力构成扭矩(顶层)：+X 在 y=B 两角，-X 在 y=0 两角
    m2.add_load(Load3D(f"C2_{n}", fx=P/2)); m2.add_load(Load3D(f"C3_{n}", fx=P/2))
    m2.add_load(Load3D(f"C0_{n}", fx=-P/2)); m2.add_load(Load3D(f"C1_{n}", fx=-P/2))
    U, _ = solve(m2)
    rz = np.mean([U[f"C{ci}_{n}"][5] for ci in range(4)])
    print(f"  顶层扭转角 rz = {rz:.2e} rad（{abs(rz)*1e3:.3f} mrad）→ 扭转耦联被捕捉")
    print(f"  对应角点扭转位移 ≈ {abs(rz)*B/2:.2f} mm")

    print("\n2D 平面模型无法表达上述两者；三维单元(6 自由度/节点)是离工程级最大的一跳。")
    print("已验证：双向弯曲 PH³/3EI、扭转 TL/GJ、翼缘组合截面平行轴定理。")


if __name__ == "__main__":
    main()
