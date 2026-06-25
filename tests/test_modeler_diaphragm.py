import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from modeler.build.to_frame3d import build_frame3d
from structdesign.analysis.modal3d import rigid_diaphragm_modal, flexible_diaphragm_periods
from structdesign.frame3d_builder import floor_masses

B = 6000


def _grid(nx, ny, diaphragm="rigid"):
    xs = [i * B for i in range(nx + 1)]; ys = [k * B for k in range(ny + 1)]
    cols = [Column(x, y, 500, 500) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(nx)] +
             [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(ny)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 3)],
                   seismic=Seismic(n_modes=9, diaphragm=diaphragm))


def test_flexible_period_ge_rigid():
    # 守恒：刚性楼盖=柔性的带约束子空间 → T_flex ≥ T_rigid
    p = _grid(3, 3)
    model = build_frame3d(p)
    fm = floor_masses(model, 1.0)
    rigid = rigid_diaphragm_modal(model, fm)
    flex = flexible_diaphragm_periods(model, fm, n=3)
    assert flex, "柔性周期为空"
    assert flex[0] >= rigid.T1 - 1e-6, (flex[0], rigid.T1)


def test_framed_floor_is_effectively_rigid():
    # 梁框成的楼盖：梁轴向刚度大 → 第一周期(平动)对楼盖刚柔几乎不敏感 → 验证刚性假定对 T1 成立。
    # (注：楼盖平面内柔性主要影响平面内/扭转高阶模态与内力分配，非基本平动周期 T1。)
    p = _grid(3, 3)
    model = build_frame3d(p); fm = floor_masses(model, 1.0)
    rigid = rigid_diaphragm_modal(model, fm)
    flex = flexible_diaphragm_periods(model, fm, n=3)
    div = (flex[0] - rigid.T1) / rigid.T1
    assert 0 <= div < 0.05, div          # 满布梁→ T1 对楼盖假定不敏感


def test_analyze_reports_flexible_when_elastic():
    OUT = os.path.join(os.path.dirname(__file__), "_dia_out")
    p = _grid(6, 1, diaphragm="elastic")
    r = analyze(p, OUT)
    assert r.diaphragm == "elastic"
    assert r.T1_flexible >= r.T1 - 1e-6, (r.T1_flexible, r.T1)
    assert any("楼盖敏感性" in row[0] for row in r.checks_table)
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


def test_rigid_default_no_flexible():
    OUT = os.path.join(os.path.dirname(__file__), "_dia_out")
    p = _grid(3, 3)            # 默认 rigid
    r = analyze(p, OUT)
    assert r.diaphragm == "rigid"
    assert r.T1_flexible == 0.0
    assert not any("楼盖刚柔对比" in row[0] for row in r.checks_table)
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
