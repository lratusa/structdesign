"""
完整地上抗震设计 demo —— 全链路一次跑通。

模态→反应谱→层地震力→整榀框架重力+地震工况→荷载组合→能力设计→梁柱配筋。
运行：python demo_building_seismic.py → 生成 计算书_地上抗震设计.md
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.frame_spec import SecBox
from structdesign.design_building import seismic_frame_design
from structdesign import rebar as rb


def col():
    return SecBox(650, 650, "C40", "column", h_max=1200, seismic_grade="三级")


def beam():
    return SecBox(300, 700, "C30", "beam", h_max=1000, seismic_grade="三级")


def main():
    story_mass = 3.0e5
    bd = seismic_frame_design(
        n_bays=3, n_stories=6, bay_w=6000, story_h=3600,
        col_factory=col, beam_factory=beam, w_gravity=55.0,
        story_mass=story_mass, alpha_max=0.08, Tg=0.40, seismic_grade="三级")
    shear_weight = bd.base_shear / (6 * story_mass * 9.81) * 100

    print("=" * 60)
    print("完整地上抗震设计 · 3跨×6层 · 7度多遇 · 三级抗震")
    print("=" * 60)
    print(f"T1={bd.T1:.3f}s   基底剪力={bd.base_shear/1e3:.0f}kN   剪重比={shear_weight:.2f}%")
    n_bad = sum(0 if m.ok else 1 for m in bd.members.values())
    print(f"全部 {len(bd.members)} 构件，截面不足/超限 {n_bad} 个")
    print("\n底层构件（重力弯矩 → 含地震组合 → 能力设计 → 配筋）：")
    show = ["Z0_1", "Z1_1", "Z2_1", "L0_1", "L1_1", "Z0_6"]
    for mid in show:
        m = bd.members[mid]
        bars = rb.select_bars(m.As / (2 if m.kind == "column" else 1), 400)
        lab = (f"2×{bars.label()}" if m.kind == "column" else bars.label())
        flag = "✔" if m.ok else "✗"
        print(f"  {mid:6s}[{m.kind:6s}]{flag} Mg={m.M_gravity:6.1f} → 组合={m.M_combo:6.1f} "
              f"→ 能力={m.M_capacity:6.1f} kN·m  N={m.N:6.0f}kN  {lab:9s} {m.note}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_地上抗震设计.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 结构计算书 —— 地上结构抗震设计（全链路）\n\n")
        f.write("数据流：模态分析→GB50011反应谱→层地震力→整榀框架(重力+地震)→")
        f.write("荷载组合(GB50009)→能力设计(强柱弱梁/强剪弱弯)→配筋。\n\n")
        f.write(f"- 规模：3跨×6层，柱500×500 C40，梁300×600 C30；二级抗震\n")
        f.write(f"- 地震：8度多遇 αmax=0.16，II类场地 Tg=0.40\n")
        f.write(f"- **自振周期 T1={bd.T1:.3f}s；基底剪力 V0={bd.base_shear/1e3:.0f}kN**\n\n")
        f.write("## 楼层剪力 (kN)\n\n| 层 | 层剪力V |\n|---|---|\n")
        for i, v in enumerate(bd.story_shears, 1):
            f.write(f"| {i} | {v/1e3:.0f} |\n")
        f.write("\n## 构件配筋（节选底层）\n\n")
        f.write("| 构件 | 类型 | 重力M | 组合M | 能力设计M | N(kN) | As(mm²) | 备注 |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for mid in show:
            m = bd.members[mid]
            f.write(f"| {mid} | {m.kind} | {m.M_gravity:.1f} | {m.M_combo:.1f} | "
                    f"{m.M_capacity:.1f} | {m.N:.0f} | {m.As:.0f} | {m.note} |\n")
        f.write("\n> 周期/振型经解析解验证；地震力按SRSS组合；柱弯矩经强柱弱梁放大。"
                "须由注册结构工程师复核签字。\n")
    print(f"\n计算书: {out}")


if __name__ == "__main__":
    main()
