"""
平法出图 demo —— 从配筋结果生成梁平法配筋图(SVG) + 集中标注。

运行：python demo_drawing.py → 生成 配筋图_KL1.svg
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign.codes import gb50010_beam as gb
from structdesign import rebar as rb
from structdesign.drawing.pingfa import BeamPingfa, save_beam_svg, sym


def main():
    b, h, cg, rg = 250, 600, "C30", "HRB400"
    a_s = 40
    # 支座负弯矩 → 上部筋；跨中正弯矩 → 下部筋
    fl_sup = gb.design_flexure(b, h, 220, cg, rg, a_s=a_s)
    fl_mid = gb.design_flexure(b, h, 160, cg, rg, a_s=a_s)
    As_min, _ = gb.min_tension_area(b, h, cg, rg)
    sup_bars = rb.select_bars(max(fl_sup.As, As_min), b)
    mid_bars = rb.select_bars(max(fl_mid.As, As_min), b)
    # 受剪 → 箍筋间距
    sh = gb.design_shear(b, h, 200, cg, "HPB300", a_s=a_s)
    s_normal = 200 if sh.only_constructional else 150
    s_dense = 100

    sy = sym(rg)
    p = BeamPingfa(
        beam_id="KL1", n_span=2, b=b, h=h, length_mm=6600,
        stirrup_grade="HPB300", stirrup_d=8, s_dense=s_dense, s_normal=s_normal, legs=2,
        top_through="2C20",
        support_top=sup_bars.label().replace("D", sy),
        bottom=mid_bars.label().replace("D", sy),
        side_bars="G4C12",
    )

    print("平法集中标注：")
    for line in p.concentrated_annotation():
        print("  " + line)
    print(f"原位：支座上部 {p.support_top}，跨中下部 {p.bottom}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "配筋图_KL1.svg")
    save_beam_svg(p, out)
    print(f"\n配筋图: {out}")


if __name__ == "__main__":
    main()
