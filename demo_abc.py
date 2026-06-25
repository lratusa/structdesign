"""
abc 综合 demo：
  (c) 楼板荷载导算 → 梁线荷载
  (a) P-Δ 二阶效应放大地震弯矩
  (b) 平法配筋图导出 DXF（单梁 + 整楼批量）

运行：python demo_abc.py → 生成 配筋图_KL1.dxf 与 配筋图_整楼批量.dxf
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structdesign import loads_takedown as td
from structdesign.frame_spec import SecBox
from structdesign.design_building import seismic_frame_design
from structdesign.drawing.pingfa import BeamPingfa
from structdesign.drawing.pingfa_dxf import beam_dxf, batch_beams_dxf

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 60)
    print("(c) 楼板/次梁竖向荷载导算")
    print("=" * 60)
    q = td.slab_q(dead_kpa=5.0, live_kpa=2.0)      # 设计面荷载
    print(f"面荷载设计值 q = 1.3·5 + 1.5·2 = {q} kN/m²")
    one = td.one_way_udl(q, beam_spacing=3.0)
    print(f"单向板(梁间距3m): 梁线荷载 w = {one} kN/m")
    tw = td.two_way_beam_loads(q, lx=4.0, ly=6.0)
    print(f"双向板 4×6m: 短边梁 w={tw.w_short:.2f}, 长边梁 w={tw.w_long:.2f} kN/m "
          f"(Σ校验={2*tw.w_short*tw.lx + 2*tw.w_long*tw.ly:.1f}=q·A={tw.total_load:.1f}✔)")

    print("\n" + "=" * 60)
    print("(a) P-Δ 二阶效应放大地震弯矩")
    print("=" * 60)

    def run(pd):
        return seismic_frame_design(3, 8, 6000, 3600,
            lambda: SecBox(500, 500, "C40", "column", h_max=1200, seismic_grade="二级"),
            lambda: SecBox(300, 650, "C30", "beam", h_max=1200, seismic_grade="二级"),
            70.0, 5.0e5, 0.16, 0.40, "二级", pdelta=pd)
    a, b = run(False), run(True)
    print(f"整体屈曲系数 λcr={a.stability:.0f}")
    for k in ["Z0_1", "Z1_1"]:
        amp = b.members[k].M_combo / a.members[k].M_combo
        print(f"  {k}: 一阶 M={a.members[k].M_combo:.0f} → 二阶 M={b.members[k].M_combo:.0f} kN·m "
              f"(放大 {amp:.3f})")

    print("\n" + "=" * 60)
    print("(b) 平法配筋图导出 DXF")
    print("=" * 60)
    p1 = BeamPingfa(beam_id="KL1", n_span=2, b=250, h=600, length_mm=6600,
                    support_top="6C22", bottom="4C25", top_through="2C20")
    f1 = beam_dxf(p1).save(os.path.join(HERE, "配筋图_KL1.dxf"))
    beams = [BeamPingfa(beam_id=f"KL{i}", n_span=2, b=300, h=600 + i * 50,
                        length_mm=6000, support_top=f"{4+i}C22", bottom=f"{3+i}C22")
             for i in range(1, 5)]
    f2 = batch_beams_dxf(beams).save(os.path.join(HERE, "配筋图_整楼批量.dxf"))
    print(f"单梁 DXF: {f1}")
    print(f"整楼批量 DXF({len(beams)}根): {f2}")


if __name__ == "__main__":
    main()
