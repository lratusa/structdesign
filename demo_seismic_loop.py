"""
最终形态 demo —— 地震工况下截面自动生长闭环。

这是项目最初愿景的完整实现："读模型→自动配筋→自动调截面→计算通过"。
起始截面故意偏小，软件每轮重算模态(周期随截面变)、反应谱、组合、能力设计、配筋，
对不满足的构件自动加大截面，直到全楼满足。无需人工反复点"重算"。

运行：python demo_seismic_loop.py → 生成 计算书_抗震自动迭代.md
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.frame_spec import SecBox
from structdesign.design_building import seismic_closed_loop


def main():
    res = seismic_closed_loop(
        n_bays=3, n_stories=6, bay_w=6000, story_h=3600,
        col_factory=lambda: SecBox(400, 400, "C40", "column", h_max=1200, seismic_grade="三级"),
        beam_factory=lambda: SecBox(250, 450, "C30", "beam", h_max=1000, seismic_grade="三级"),
        w_gravity=55.0, story_mass=3.0e5, alpha_max=0.08, Tg=0.40,
        seismic_grade="三级", h_step=50.0)

    print("=" * 64)
    print("地震工况下截面自动生长闭环 · 3跨×6层 · 7度多遇 · 三级")
    print("起始柱400×400 梁250×450(偏小) → 自动生长至满足")
    print("=" * 64)
    for h in res.history:
        print("  " + h)
    print("-" * 64)
    print(f"收敛：{'是' if res.converged else '否'}（{res.iterations} 轮）")
    print("\n最终截面（按需差异化生长）：")
    for mid in ["Z0_1", "Z1_1", "Z2_1", "Z0_6", "L0_1", "L1_3"]:
        m = res.final.members[mid]
        print(f"  {mid:6s}[{m.kind:6s}] {res.final_sections[mid]:9s}  "
              f"M={m.M_capacity:6.1f}kN·m N={m.N:5.0f}kN ρ={m.rho*100:.1f}% {'✔' if m.ok else '✗'}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_抗震自动迭代.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 结构计算书 —— 地震工况截面自动生长闭环\n\n")
        f.write("起始截面偏小，软件每轮重算模态→反应谱→组合→能力设计→配筋，")
        f.write("自动加大不足构件截面直至全楼满足。截面变→周期变→地震力重分布。\n\n")
        f.write("## 迭代过程\n\n")
        for h in res.history:
            f.write(f"- {h}\n")
        f.write(f"\n**收敛：{'是' if res.converged else '否'}，{res.iterations} 轮**\n\n")
        f.write("## 最终截面与配筋（节选）\n\n")
        f.write("| 构件 | 截面 | 能力设计M(kN·m) | N(kN) | 配筋率 | 满足 |\n|---|---|---|---|---|---|\n")
        for mid in ["Z0_1", "Z1_1", "Z2_1", "Z0_6", "L0_1", "L1_3"]:
            m = res.final.members[mid]
            f.write(f"| {mid} | {res.final_sections[mid]} | {m.M_capacity:.1f} | "
                    f"{m.N:.0f} | {m.rho*100:.1f}% | {'✔' if m.ok else '✗'} |\n")
        f.write("\n> 周期/振型经解析解验证；地震内力逐振型SRSS组合；须注册结构工程师复核签字。\n")
    print(f"\n计算书: {out}")


if __name__ == "__main__":
    main()
