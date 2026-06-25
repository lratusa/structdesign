"""
模态对比 demo —— 剪切层近似 vs 真实框架特征值。

同一 3跨×6层框架，两种方法算自振周期：
  - 剪切层：假定梁刚性，层抗侧刚度仅由柱给出 → 偏刚、周期偏短。
  - 真实框架：含梁柔度，Guyan 凝聚解特征值 → 更准、周期更长。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign import materials
from structdesign.frame_spec import SecBox, build_model
from structdesign.frame_builder import build_regular_frame
from structdesign.analysis.modal import solve_shear_building, story_stiffness_from_columns
from structdesign.analysis.frame_modal import frame_modal


def main():
    n_bays, n_stories, h = 3, 6, 3600.0
    spec = build_regular_frame(
        n_bays, n_stories, 6000, h,
        lambda: SecBox(600, 600, "C40", "column", seismic_grade="三级"),
        lambda: SecBox(300, 600, "C30", "beam", seismic_grade="三级"),
        w_gravity=0.0, lateral_per_floor=0.0)
    masses = [3.0e5] * n_stories

    # 剪切层
    E = materials.concrete("C40").Ec
    I_total = (n_bays + 1) * (600 * 600 ** 3 / 12)
    k = story_stiffness_from_columns(E, I_total, h) * 1000.0
    sb = solve_shear_building(masses, [k] * n_stories)

    # 真实框架
    fm = frame_modal(build_model(spec), masses)

    print("同一 3跨×6层框架（柱600×600，梁300×600）自振周期对比 (s)：")
    print(f"{'阶':>3} {'剪切层(假定梁刚性)':>18} {'真实框架(含梁柔度)':>18}")
    for j in range(n_stories):
        print(f"{j+1:>3} {sb.periods[j]:>18.3f} {fm.periods[j]:>18.3f}")
    print(f"\nT1：剪切层 {sb.periods[0]:.3f}s → 真实框架 {fm.periods[0]:.3f}s "
          f"(长 {(fm.periods[0]/sb.periods[0]-1)*100:.0f}%)")
    print("真实框架周期更长，因为它计入了梁的柔度——这是更接近实际的结果。")


if __name__ == "__main__":
    main()
