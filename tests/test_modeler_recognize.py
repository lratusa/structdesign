import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from modeler.io.dxf_import import import_drawing
from modeler.io.recognize import recognize, classify_layer

OUT = os.path.join(os.path.dirname(__file__), "_rec_out")
B = 6000


def _make_dxf(path):
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    for ly in ("轴线", "柱", "梁", "墙"):
        if ly not in doc.layers:
            doc.layers.add(ly)
    gx = [0, B, 2 * B]; gy = [0, B, 2 * B]
    # 轴网
    for x in gx:
        msp.add_line((x, 0), (x, 2 * B), dxfattribs={"layer": "轴线"})
    for y in gy:
        msp.add_line((0, y), (2 * B, y), dxfattribs={"layer": "轴线"})
    # 柱：9 个 500x500 闭合矩形
    for x in gx:
        for y in gy:
            s = 250
            msp.add_lwpolyline([(x - s, y - s), (x + s, y - s), (x + s, y + s), (x - s, y + s)],
                               close=True, dxfattribs={"layer": "柱"})
    # 梁：相邻柱间连线
    for y in gy:
        for i in range(2):
            msp.add_line((gx[i], y), (gx[i + 1], y), dxfattribs={"layer": "梁"})
    for x in gx:
        for k in range(2):
            msp.add_line((x, gy[k]), (x, gy[k + 1]), dxfattribs={"layer": "梁"})
    # 墙：一道平行线对(间距200) 沿 x=B, y=0..B
    msp.add_line((B - 100, 0), (B - 100, B), dxfattribs={"layer": "墙"})
    msp.add_line((B + 100, 0), (B + 100, B), dxfattribs={"layer": "墙"})
    # 一个无关图层
    if "标注" not in doc.layers:
        doc.layers.add("标注")
    msp.add_line((0, -500), (1000, -500), dxfattribs={"layer": "标注"})
    doc.saveas(path)


def test_classify_layer():
    assert classify_layer("柱") == "column"
    assert classify_layer("墙") == "wall"
    assert classify_layer("梁") == "beam"
    assert classify_layer("轴线") == "axis"
    assert classify_layer("S-COLU") == "column"
    assert classify_layer("随便") == "other"
    assert classify_layer("随便", overrides={"随便": "beam"}) == "beam"


def test_recognize_members_from_dxf():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "plan.dxf")
    _make_dxf(path)
    d = import_drawing(path)
    assert len(d.rects) == 9, ("应捕获9个柱矩形", len(d.rects))
    fl, grid, rep = recognize(d)
    assert rep["n_col"] == 9, rep
    # 柱截面 ~500x500
    assert all(abs(c.b - 500) < 5 and abs(c.h - 500) < 5 for c in fl.columns), \
        [(c.b, c.h) for c in fl.columns][:3]
    # 轴网 3x3
    assert grid.x == [0, B, 2 * B] and grid.y == [0, B, 2 * B], (grid.x, grid.y)
    # 梁: 12 根
    assert rep["n_beam"] == 12, rep["n_beam"]
    # 墙: 平行线对 → 1 道墙, 厚~200, 中线 x≈B
    assert rep["n_wall"] == 1, rep["n_wall"]
    w = fl.walls[0]
    assert abs(w.t - 200) < 5, w.t
    assert abs((w.x1 + w.x2) / 2 - B) < 5, (w.x1, w.x2)
    # 报告含未归类图层
    assert "标注" in rep["unclassified"], rep["unclassified"]
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


def test_recognize_buildable():
    # 识别结果应能直接进 Project 并计算
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "plan.dxf"); _make_dxf(path)
    d = import_drawing(path)
    fl, grid, rep = recognize(d)
    from modeler.project import Project, Storey, Seismic, SlabLoad
    fl.slab = SlabLoad(6, 2.5)
    p = Project(grid=grid, floor=fl, storeys=[Storey(3600, 3)], seismic=Seismic(n_modes=9))
    from modeler.run.analyze import analyze
    r = analyze(p, OUT)
    assert r.Tx > 0 and r.n_members > 0
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
