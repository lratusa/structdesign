import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, Wall, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from modeler import view3d

OUT = os.path.join(os.path.dirname(__file__), "_md_v3d")


def _model():
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 600, 600) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    walls = [Wall(B, B, 2 * B, B, 400)]
    fl = StandardFloor(columns=cols, beams=beams, walls=walls, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 4)], seismic=Seismic(n_modes=6))


def test_build_figures_and_export():
    os.makedirs(OUT, exist_ok=True)
    p = _model(); r = analyze(p, OUT)
    for mode in ("model", "util", "disp"):
        fig = view3d.build_figure(p, r, mode)
        # 含一个 Mesh3d 且有三角面
        mesh = fig.data[0]
        assert len(mesh.x) > 0 and len(mesh.i) > 0, mode
        html = view3d.export_html(p, r, os.path.join(OUT, f"{mode}.html"), mode)
        png = view3d.export_png(p, r, os.path.join(OUT, f"{mode}.png"), mode)
        assert os.path.getsize(html) > 100000     # 内嵌 plotly.js
        assert os.path.getsize(png) > 5000


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
