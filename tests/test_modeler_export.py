import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from modeler.project import Column, Beam, Wall, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from modeler.io.dxf_export import export_plan, export_slab_plan
from modeler.project import Slab

OUT = os.path.join(os.path.dirname(__file__), "_md_exp")


def _model():
    B = 7000
    xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 500, 500) for x in xs for y in ys]
    beams = []
    for y in ys:
        for i in range(2):
            beams.append(Beam(xs[i], y, xs[i + 1], y, 300, 600))
    for x in xs:
        for k in range(2):
            beams.append(Beam(x, ys[k], x, ys[k + 1], 300, 600))
    walls = [Wall(B, B, 2 * B, B, 400)]
    fl = StandardFloor(columns=cols, beams=beams, walls=walls, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 4)], seismic=Seismic(n_modes=6))


def test_export_dxf_png_pdf_and_table():
    os.makedirs(OUT, exist_ok=True)
    p = _model()
    r = analyze(p, OUT)
    dxf = os.path.join(OUT, "plan.dxf"); png = os.path.join(OUT, "plan.png"); pdf = os.path.join(OUT, "plan.pdf")
    dxf_out, png_out, pdf_out = export_plan(p, r, dxf, png, pdf)
    assert os.path.exists(dxf_out) and os.path.getsize(dxf_out) > 500
    doc = ezdxf.readfile(dxf_out)
    ents = list(doc.modelspace())
    assert len(ents) > 30, len(ents)
    layers = {e.dxf.layer for e in ents}
    assert {"COLUMN", "BEAM", "AXIS", "TABLE"} <= layers, layers
    # 柱表表头文字存在
    texts = [e.dxf.text for e in ents if e.dxftype() in ("TEXT", "MTEXT")]
    assert any("SCHEDULE" in t for t in texts), "缺柱表"
    assert any(t.startswith("KZ1") for t in texts), "缺 KZ 编号"
    assert any(t.startswith("KL1") for t in texts), "缺 KL 集中标注"
    assert any("SECTION DETAILS" in t for t in texts), "缺截面大样"
    assert any("TAKE-OFF" in t for t in texts), "缺材料统计"
    # 墙施工图：墙表 + Q 编号
    assert any("WALL SCHEDULE" in t for t in texts), "缺墙表"
    assert any(t.startswith("Q1") for t in texts), "缺 Q 墙编号"
    # 跨构件钢筋归并：梁表 + KL 编号 + 归并比
    assert any("BEAM SCHEDULE" in t for t in texts), "缺梁表"
    assert r.n_beam_total > 0 and 0 < r.n_beam_marks <= r.n_beam_total, (r.n_beam_total, r.n_beam_marks)
    # 柱表箍筋应为计算值(C..@../..)而非空
    assert any("@" in t and t.startswith("C") for t in texts), "缺箍筋标注"
    # PNG + PDF 生成
    assert png_out and os.path.exists(png_out) and os.path.getsize(png_out) > 2000
    assert pdf_out and os.path.exists(pdf_out) and os.path.getsize(pdf_out) > 2000


def test_beam_has_top_bottom():
    p = _model()
    r = analyze(p, OUT)
    bm = [m for m in r.members if m["kind"] == "梁"][0]
    assert "bars_top" in bm and "bars_bot" in bm


def test_slab_plan_drawing():
    os.makedirs(OUT, exist_ok=True)
    p = _model()
    # 在各区格布板
    B = 7000
    p.floor.slabs = [Slab(0, 0, B, B, 120), Slab(B, 0, 2 * B, B, 120),
                     Slab(0, B, B, 2 * B, 120), Slab(B, B, 2 * B, 2 * B, 120)]
    r = analyze(p, OUT)
    # 板设计含支座负筋
    assert all("bars_x_top" in sd for sd in r.slabs), "缺支座负筋"
    dxf = os.path.join(OUT, "slab.dxf"); png = os.path.join(OUT, "slab.png")
    dxf_out, png_out, _ = export_slab_plan(p, r, dxf, png)
    assert os.path.exists(dxf_out)
    doc = ezdxf.readfile(dxf_out)
    ents = list(doc.modelspace())
    layers = {e.dxf.layer for e in ents}
    assert {"SBOT", "STOP", "SLAB"} <= layers, layers       # 板底/板面/轮廓层都有
    texts = [e.dxf.text for e in ents if e.dxftype() in ("TEXT", "MTEXT")]
    assert any("SLAB SCHEDULE" in t for t in texts)
    assert any(t.startswith("LB1") for t in texts)
    assert png_out and os.path.exists(png_out)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc()
            print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
