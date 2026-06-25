import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project, Thermal
from modeler.build.to_frame3d import build_with_meta, build_frame3d
from modeler.run.temperature import thermal_node_loads
from modeler.run.analyze import analyze


def _wide(nx=4, ny=2, bay=6000, n_storeys=3):
    cols = [Column(i * bay, k * bay, 600, 600) for i in range(nx + 1) for k in range(ny + 1)]
    beams = ([Beam(i * bay, k * bay, (i + 1) * bay, k * bay, 300, 600) for k in range(ny + 1) for i in range(nx)] +
             [Beam(i * bay, k * bay, i * bay, (k + 1) * bay, 300, 600) for i in range(nx + 1) for k in range(ny)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6.0, 2.5))
    gx = [i * bay for i in range(nx + 1)]; gy = [k * bay for k in range(ny + 1)]
    return Project(grid=Grid(gx, gy), floor=fl, storeys=[Storey(3600, n_storeys)],
                   seismic=Seismic(n_modes=9))


def test_thermal_loads_self_equilibrated():
    p = _wide()
    model, meta = build_with_meta(p)
    beam_ids = [mid for mid, mm in meta.items() if mm["kind"] == "梁"]
    loads = thermal_node_loads(model, beam_ids, 30.0)
    assert loads, "无热荷载"
    sx = sum(l.fx for l in loads); sy = sum(l.fy for l in loads); sz = sum(l.fz for l in loads)
    assert abs(sx) < 1e-3 and abs(sy) < 1e-3 and abs(sz) < 1e-3, (sx, sy, sz)   # 自平衡


def test_thermal_load_scales_linearly():
    p = _wide()
    model, meta = build_with_meta(p)
    beam_ids = [mid for mid, mm in meta.items() if mm["kind"] == "梁"]
    l1 = thermal_node_loads(model, beam_ids, 20.0)
    l2 = thermal_node_loads(model, beam_ids, 40.0)
    a = sum(abs(l.fx) for l in l1); b = sum(abs(l.fx) for l in l2)
    assert abs(b - 2 * a) < 1e-6 * max(b, 1.0), (a, b)        # ΔT 翻倍 → 力翻倍


def test_thermal_axial_direction():
    # 沿 +x 的梁：ni 端受 -P(x)，nj 端受 +P(x)
    p = _wide(nx=1, ny=1)
    model, meta = build_with_meta(p)
    bid = next(mid for mid, mm in meta.items() if mm["kind"] == "梁")
    m = model.members[bid]
    loads = thermal_node_loads(model, [bid], 25.0)
    li = next(l for l in loads if l.node == m.ni)
    lj = next(l for l in loads if l.node == m.nj)
    # 一端 x 分量为正、另一端为负（自由膨胀把两端外推）
    assert li.fx * lj.fx < 0, (li.fx, lj.fx)


def _max_col_M(r):
    return max((mb.get("M", 0.0) for mb in r.members if mb["kind"] == "柱"), default=0.0)


def test_thermal_disabled_no_effect():
    out = os.path.join(os.path.dirname(__file__), "_tm_out")
    p = _wide(); p.thermal = Thermal(enabled=False)
    r = analyze(p, out)
    assert r.thermal_on is False
    assert r.thermal_col_M == 0.0


def test_thermal_enabled_induces_column_moment_and_scales():
    out = os.path.join(os.path.dirname(__file__), "_tm_out")
    p25 = _wide(); p25.thermal = Thermal(enabled=True, dT=25.0)
    r25 = analyze(p25, out)
    assert r25.thermal_on is True
    assert r25.thermal_col_M > 0.0, r25.thermal_col_M           # 端柱出现温度弯矩
    p50 = _wide(); p50.thermal = Thermal(enabled=True, dT=50.0)
    r50 = analyze(p50, out)
    # 线性：ΔT 翻倍 → 温度柱弯矩约翻倍
    assert abs(r50.thermal_col_M - 2 * r25.thermal_col_M) < 0.05 * r50.thermal_col_M, \
        (r25.thermal_col_M, r50.thermal_col_M)


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
