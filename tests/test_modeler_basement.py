import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import (Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid,
                             Project, Basement)
from modeler.run.basement import design_basement, short_columns
from modeler.run.analyze import analyze

B = 7000
OUT = os.path.join(os.path.dirname(__file__), "_bsmt_out")


def _model(col=500, storey=3600, basement=None):
    xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, col, col) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)] +
             [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    p = Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(storey, 4)], seismic=Seismic(n_modes=6))
    if basement:
        p.basement = basement
    return p


def test_basement_disabled_none():
    assert design_basement(_model(), {}) is None


def test_basement_wall_design():
    p = _model(basement=Basement(enabled=True, n_levels=2, height=3600,
                                 wall_t=300, soil_gamma=18, K0=0.5, water_depth=1.0))
    b = design_basement(p, {"conc_total": 200.0})
    assert b is not None
    assert b["H"] == 2 * 3.6                       # 总深
    assert b["M_design"] > 0 and b["As_req"] > 0
    assert b["anti_float_Kf"] > 0


def test_anti_float_lower_with_higher_water():
    p1 = _model(basement=Basement(enabled=True, n_levels=2, water_depth=5.0))   # 水位深→水头小
    p2 = _model(basement=Basement(enabled=True, n_levels=2, water_depth=0.0))   # 水位至地面→水头大
    b1 = design_basement(p1, {"conc_total": 200.0})
    b2 = design_basement(p2, {"conc_total": 200.0})
    assert b2["anti_float_Kf"] < b1["anti_float_Kf"], (b2["anti_float_Kf"], b1["anti_float_Kf"])


def test_short_column_detection():
    # 正常层高+小柱 → 非短柱
    sc1 = short_columns(_model(col=500, storey=3600), 3600, beam_h=600)
    assert sc1["n_short"] == 0, sc1
    # 大柱(900) → 净高/柱<4 → 短柱
    sc2 = short_columns(_model(col=900, storey=3600), 3600, beam_h=600)
    assert sc2["n_short"] >= 1, sc2
    # 错层/矮层(层高1800) → 短柱
    sc3 = short_columns(_model(col=500, storey=1800), 1800, beam_h=600)
    assert sc3["n_short"] >= 1, sc3


def test_analyze_integrates_basement_and_shortcol():
    p = _model(col=900, basement=Basement(enabled=True, n_levels=2, water_depth=0.5))
    r = analyze(p, OUT)
    assert r.basement and r.basement["M_design"] > 0
    assert r.n_short_col >= 1                       # 900 柱→短柱
    labels = [row[0] for row in r.checks_table]
    assert any("地下室外墙" in x for x in labels)
    assert any("地下室抗浮" in x for x in labels)
    assert any("短柱" in x for x in labels)
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    import shutil; shutil.rmtree(OUT, ignore_errors=True)
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
