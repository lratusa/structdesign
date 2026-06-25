"""
P-Δ / 屈曲 demo —— 欧拉解析解验证 + 整榀框架整体稳定。

(1) 铰接柱与悬臂柱屈曲临界荷载与欧拉解对比。
(2) 整榀框架重力下的屈曲系数 λcr（整体稳定裕度，>10 则 P-Δ 可忽略）。
"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.analysis.frame2d import FrameModel, Node, Member, NodalLoad
from structdesign.analysis.pdelta import buckling_factor
from structdesign.frame_spec import SecBox, build_model
from structdesign.frame_builder import build_regular_frame


def euler_column(restraint_bot, restraint_top, mu, label):
    L, E, I, P0, n = 4000.0, 2e5, 8.333e6, 1000.0, 6
    m = FrameModel()
    for i in range(n + 1):
        r = restraint_bot if i == 0 else (restraint_top if i == n else (False, False, False))
        m.add_node(Node(str(i), 0, L * i / n, r))
    for i in range(n):
        m.add_member(Member(f"e{i}", str(i), str(i + 1), E, 1e4, I))
    m.add_load(NodalLoad(str(n), Fy=-P0))
    Pcr = buckling_factor(m) * P0
    Pe = math.pi ** 2 * E * I / (mu * L) ** 2
    print(f"  {label:12s} Pcr(计算)={Pcr/1e3:8.1f} kN   欧拉解={Pe/1e3:8.1f} kN   "
          f"误差 {(Pcr/Pe-1)*100:+.1f}%")


def main():
    print("一、屈曲临界荷载 vs 欧拉解析解")
    euler_column((True, True, False), (True, False, False), 1.0, "铰接-铰接")
    euler_column((True, True, True), (False, False, False), 2.0, "悬臂(固-自由)")

    print("\n二、整榀框架整体稳定（重力下屈曲系数 λcr）")
    for (b, h, lab) in [(700, 700, "粗壮柱700"), (450, 450, "细柱450")]:
        spec = build_regular_frame(
            3, 6, 6000, 3600,
            lambda b=b, h=h: SecBox(b, h, "C40", "column", seismic_grade="三级"),
            lambda: SecBox(300, 600, "C30", "beam", seismic_grade="三级"),
            w_gravity=80.0, lateral_per_floor=0.0)
        lam = buckling_factor(build_model(spec))
        flag = "P-Δ可忽略" if lam > 10 else "需计入P-Δ"
        print(f"  {lab}: λcr={lam:7.1f}  ({flag})")
    print("\n柱越细 → 屈曲系数越低 → 整体稳定越差，需计入二阶效应。")


if __name__ == "__main__":
    main()
