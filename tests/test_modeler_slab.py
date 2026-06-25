import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.run.slab_design import design_slab, auto_slabs, slab_spans
from modeler.project import Slab


def test_two_way_square():
    r = design_slab(6.0, 6.0, 120, 8.0)
    assert r["kind"] == "双向板"
    # 方形板两方向弯矩/配筋相近
    assert abs(r["Asx"] - r["Asy"]) / max(r["Asx"], 1) < 0.05
    assert r["bars_x"].startswith("C") and "@" in r["bars_x"]


def test_one_way():
    r = design_slab(3.0, 8.0, 100, 8.0)
    assert r["kind"] == "单向板"
    assert r["Asx"] >= r["Asy"]           # 主受力方向配筋更大


def test_min_reinforcement_floor():
    r = design_slab(2.0, 2.0, 120, 4.0)   # 小板小荷载 → 构造配筋控制
    assert r["Asx"] >= 0.0015 * 1000 * 120 - 1


def test_thickness_check():
    thin = design_slab(7.0, 7.0, 80, 8.0)   # 7m 板才 80 厚 → 不满足
    thick = design_slab(7.0, 7.0, 200, 8.0)
    assert not thin["ok"] and thick["ok"]


def test_auto_slabs():
    s = auto_slabs([0, 6000, 12000], [0, 6000, 12000], 120)
    assert len(s) == 4                      # 2x2 区格
    assert all(isinstance(x, Slab) for x in s)
    Lx, Ly = slab_spans(s[0])
    assert Lx == 6.0 and Ly == 6.0


def test_analyze_and_export_with_slabs():
    import ezdxf
    from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
    from modeler.run.analyze import analyze
    from modeler.io.dxf_export import export_plan
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 600, 600) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    p = Project(grid=Grid(xs, ys),
                floor=StandardFloor(columns=cols, beams=beams, walls=[],
                                    slabs=auto_slabs(xs, ys, 150), slab=SlabLoad(6, 2.5)),
                storeys=[Storey(3600, 4)], seismic=Seismic(n_modes=6))
    out = os.path.join(os.path.dirname(__file__), "_md_slabint")
    r = analyze(p, out)
    assert len(r.slabs) == 4 and r.slabs[0]["name"] == "LB1"
    d, _, _ = export_plan(p, r, os.path.join(out, "p.dxf"), None, None)
    txts = [e.dxf.text for e in ezdxf.readfile(d).modelspace() if e.dxftype() == "TEXT"]
    assert any("SLAB SCHEDULE" in t for t in txts)
    assert any(t.startswith("LB1") for t in txts)


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
