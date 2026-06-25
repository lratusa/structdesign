import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from modeler.run.foundation import design_footings
from modeler.run.stairs import design_stair
from modeler.io.dxf_export import export_foundation, export_stair

OUT = os.path.join(os.path.dirname(__file__), "_md_fs")


def _model():
    B = 7500; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 600, 600) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, walls=[], slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 6)],
                   seismic=Seismic(n_modes=6), fak=200)


def test_footing_design_and_export():
    os.makedirs(OUT, exist_ok=True)
    p = _model(); r = analyze(p, OUT)
    footings, rows = design_footings(p, r, fak=200)
    assert len(footings) == 9, len(footings)
    assert rows and rows[0][0].startswith("JC")
    # 尺寸合理：每个基础边长 ≥ 柱宽
    assert all(f["B"] * 1000 >= 600 for f in footings.values())
    d, png, pdf = export_foundation(p, r, os.path.join(OUT, "f.dxf"),
                                    os.path.join(OUT, "f.png"), os.path.join(OUT, "f.pdf"), fak=200)
    texts = [e.dxf.text for e in ezdxf.readfile(d).modelspace() if e.dxftype() == "TEXT"]
    assert any("FOOTING" in t for t in texts)
    assert any(t.startswith("JC1") for t in texts)
    assert os.path.exists(png) and os.path.exists(pdf)


def test_stair_design_and_export():
    os.makedirs(OUT, exist_ok=True)
    s = design_stair(floor_h=3600)
    assert s["n"] % 2 == 0 and 140 <= s["riser"] <= 185, s["riser"]
    assert s["t"] >= 100 and s["bars"].startswith("C")
    d, png, pdf = export_stair(s, os.path.join(OUT, "st.dxf"),
                               os.path.join(OUT, "st.png"), os.path.join(OUT, "st.pdf"))
    texts = [e.dxf.text for e in ezdxf.readfile(d).modelspace() if e.dxftype() == "TEXT"]
    assert any("SECTION" in t for t in texts) and any("PLAN" in t for t in texts)
    assert os.path.exists(png) and os.path.exists(pdf)


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
