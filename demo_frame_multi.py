"""
多层多跨整榀框架 demo —— 闭环在真实规模框架上自动收敛。

3 跨 × 5 层框架（24 节点 / 35 构件），重力均布 + 逐层水平力。
柱初始偏小，闭环自动逐层生长截面、每轮重新有限元分析、内力重分布，直至全部满足。

运行：python demo_frame_multi.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.frame_builder import build_regular_frame
from structdesign.frame_spec import SecBox
from structdesign.design_frame import closed_loop_design


def main():
    spec = build_regular_frame(
        n_bays=3, n_stories=5, bay_w=6000, story_h=3600,
        col_sec=lambda: SecBox(350, 350, "C40", "column", h_max=1000, seismic_grade="二级"),
        beam_sec=lambda: SecBox(300, 550, "C30", "beam", h_max=1000, seismic_grade="二级"),
        w_gravity=100.0, lateral_per_floor=90000.0)

    print("=" * 60)
    print(f"整榀框架：3跨×5层  节点{len(spec.nodes)}  构件{len(spec.members)}")
    print("=" * 60)
    res = closed_loop_design(spec, h_step=50.0, max_iter=40)
    for line in res.history:
        print("  " + line[:96] + ("…" if len(line) > 96 else ""))
    print("-" * 60)
    print(f"引擎：{res.engine}　收敛：{'是' if res.converged else '否'}（{res.iterations} 轮）")

    cols = sorted(k for k in res.final_sections if k.startswith("Z"))
    over = [k for k in cols if "✗" in res.final_forces[k]]
    print(f"柱 {len(cols)} 根，仍超限 {len(over)} 根")
    print("\n底层柱最终截面（应大于顶层）：")
    for k in cols:
        if k.endswith("_1") or k.endswith(f"_{5}"):
            print(f"  {k}: {res.final_sections[k]:16s} {res.final_forces[k]}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_整榀框架.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 结构计算书 —— 整榀框架闭环（3跨×5层）\n\n")
        f.write(f"引擎：{res.engine}；收敛 {res.iterations} 轮。\n\n## 迭代过程\n\n")
        for line in res.history:
            f.write(f"{line}\n\n")
        f.write("## 最终配筋（节选）\n\n| 构件 | 截面 | 内力/校核 | 配筋 |\n|---|---|---|---|\n")
        for k in sorted(res.final_sections):
            f.write(f"| {k} | {res.final_sections[k]} | {res.final_forces[k]} | {res.reinforcement[k]} |\n")
    print(f"\n计算书: {out}")


if __name__ == "__main__":
    main()
