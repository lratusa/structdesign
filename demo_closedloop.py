"""
真实闭环 demo —— 截面自动生长 + 有限元重分析 + 内力重分布。

门式框架：两根柱(初始偏小，轴压比超限) + 一根梁(重力均布)，柱顶有上部传来的竖向力
与水平力。软件自动：分析→校核轴压比/受弯→在建筑可行域内生长截面→重新有限元分析
（刚度变、内力重分布）→ 直到全部满足。无需人工反复点"计算"。

运行：python demo_closedloop.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.analysis.frame2d import NodalLoad
from structdesign.design_frame import SecBox, FrameSpec, closed_loop_design


def main():
    H = 3600.0
    Lb = 7000.0
    cL = SecBox(b=350, h=350, concrete="C40", kind="column", h_max=900, seismic_grade="二级")
    cR = SecBox(b=350, h=350, concrete="C40", kind="column", h_max=900, seismic_grade="二级")
    bm = SecBox(b=300, h=500, concrete="C30", kind="beam", h_max=1000, seismic_grade="二级")

    spec = FrameSpec(
        nodes={
            "1": (0, 0, (True, True, True)),
            "2": (0, H, (False, False, False)),
            "3": (Lb, H, (False, False, False)),
            "4": (Lb, 0, (True, True, True)),
        },
        members={
            "C1": ("1", "2", cL, 0.0),
            "B1": ("2", "3", bm, 45.0),   # 45 N/mm = 45 kN/m 重力
            "C2": ("4", "3", cR, 0.0),
        },
        loads=[
            NodalLoad("2", Fx=120000, Fy=-2600000),   # 上部竖向2600kN + 水平120kN
            NodalLoad("3", Fy=-2600000),
        ],
    )

    res = closed_loop_design(spec, h_step=50.0)

    print("=" * 60)
    print("真实外层闭环：截面生长 + 有限元重分析 + 内力重分布")
    print("=" * 60)
    for line in res.history:
        print("  " + line)
    print("-" * 60)
    print(f"收敛: {'是' if res.converged else '否'}（共 {res.iterations} 轮）")
    print("\n最终截面 / 内力 / 配筋：")
    for mid in res.final_sections:
        print(f"  {mid}: {res.final_sections[mid]:18s} | {res.final_forces[mid]:24s} | {res.reinforcement[mid]}")

    # 写计算书片段
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_闭环迭代.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 结构计算书 —— 截面自动生长闭环迭代记录\n\n")
        f.write("门式框架；柱初始 350×350(轴压比超限)，软件自动生长并每轮重新有限元分析。\n\n")
        f.write("## 迭代过程（每轮：分析→校核→生长→重分析）\n\n")
        for i, line in enumerate(res.history, 1):
            f.write(f"{line}\n\n")
        f.write(f"**收敛：{'是' if res.converged else '否'}，共 {res.iterations} 轮**\n\n")
        f.write("## 最终结果\n\n")
        f.write("| 构件 | 截面 | 内力/校核 | 配筋 |\n|------|------|----------|------|\n")
        for mid in res.final_sections:
            f.write(f"| {mid} | {res.final_sections[mid]} | {res.final_forces[mid]} | {res.reinforcement[mid]} |\n")
        f.write("\n> 内力随截面生长自动重分布，由内置 2D 杆系有限元每轮重算；"
                "外部引擎(ETABS/YJK)可经 Analyzer 接口替换。\n")
    print(f"\n计算书: {out}")


if __name__ == "__main__":
    main()
