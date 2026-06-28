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
    for mode in ("model", "load", "util", "disp"):
        fig = view3d.build_figure(p, r, mode)
        # 含一个 Mesh3d 且有三角面
        mesh = fig.data[0]
        assert len(mesh.x) > 0 and len(mesh.i) > 0, mode
        html = view3d.export_html(p, r, os.path.join(OUT, f"{mode}.html"), mode)
        png = view3d.export_png(p, r, os.path.join(OUT, f"{mode}.png"), mode)
        assert os.path.getsize(html) > 100000     # 内嵌 plotly.js
        assert os.path.getsize(png) > 5000


def test_torsion_mode_animation_is_rotational():
    """地震扭转动画：选到的'扭转'振型应是绕楼层中心的纯转动(四角 r×u 同号)。"""
    os.makedirs(OUT, exist_ok=True)
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 500, 500) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, walls=[Wall(0, 0, 0, 2 * B, 300)],
                       slab=SlabLoad(6, 2.5))                       # 偏心墙→明显扭转
    p = Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 5)], seismic=Seismic(n_modes=12))
    from modeler.build.to_frame3d import build_with_meta
    from structdesign.analysis.modal3d import rigid_diaphragm_modal
    from structdesign.frame3d_builder import floor_masses
    m, meta = build_with_meta(p)
    zk = list(floor_masses(m, 1.0).keys()); mpf = max((6 + 1.25) * 196 * 100, 3e5)
    modal = rigid_diaphragm_modal(m, {z: mpf for z in zk})
    j, desc = view3d._pick_mode_column(modal, "扭转")
    assert "扭转" in desc and "T=" in desc and "T=0.00" not in desc, desc   # 真实周期
    disp = view3d._mode_nodal_disp(m, modal, j)
    top = max(round(n.z, 3) for n in m.nodes.values())

    def corner(X, Y):
        return next(i for i, n in m.nodes.items()
                    if abs(n.z - top) < 1 and abs(n.x - X) < 1 and abs(n.y - Y) < 1)
    crosses = []
    for (X, Y) in [(0, 0), (2 * B, 0), (2 * B, 2 * B), (0, 2 * B)]:
        d = disp[corner(X, Y)]; rx, ry = X - B, Y - B
        crosses.append(rx * d[1] - ry * d[0])          # (r×u)_z
    assert all(c > 0 for c in crosses) or all(c < 0 for c in crosses), crosses   # 纯转动
    html = view3d.export_mode_animation(p, None, os.path.join(OUT, "anim.html"), "扭转")
    assert os.path.getsize(html) > 100000


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
