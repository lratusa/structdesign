"""
demo — 端到端：定义一根梁 → 自动配筋 → 生成结构计算书。

运行：python demo.py
输出：控制台摘要 + 写出 计算书_梁KL1.md
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.model import Beam, RectSection, BeamForces
from structdesign.design_beam import design_beam
from structdesign.report.calcbook import beam_calcbook


def main():
    # 一根两端固定的框架梁 KL1，C30 + HRB400 纵筋 + HPB300 箍筋
    beam = Beam(
        name="KL1",
        section=RectSection(b=250, h=500, concrete="C30",
                            as_bottom=40, as_top=40),
        span=6000,
        main_rebar_grade="HRB400",
        stirrup_grade="HPB300",
    )
    # 三个控制截面（已是组合包络后的设计内力）
    beam.add_forces(BeamForces(M=-180, V=180, location="支座(梁顶受拉)"))
    beam.add_forces(BeamForces(M=150, V=120, location="跨中(梁底受拉)"))
    beam.add_forces(BeamForces(M=-200, V=180, location="支座(另一端)"))

    result = design_beam(beam)

    # 控制台摘要
    print("=" * 56)
    print(f"梁 {beam.name}  截面 {beam.section.b}×{beam.section.h}  {beam.section.concrete}")
    print("=" * 56)
    for sd in result.sections:
        print(f"  {sd.location:18s} M={sd.M:>6} kN·m  需As={sd.As_governing:7.0f}  "
              f"配 {sd.bars.label():8s} ({sd.As_prov:.0f})")
    if result.shear:
        sh = result.shear
        print(f"  受剪 Vmax={sh.V} kN  箍筋 {sh.stirrup}  ρsv={sh.rho_sv*100:.3f}%")
    print(f"  总体：{'通过' if result.overall_ok else '存在不满足项'}")

    # 生成计算书
    md = beam_calcbook(result, project="智能配筋示例工程")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "计算书_梁KL1.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n计算书已生成: {out}")


if __name__ == "__main__":
    main()
