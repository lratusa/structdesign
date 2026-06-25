import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.loadcode import live_reduction_vertical, beam_live_reduction
import modeler.run.analyze as az


def test_vertical_reduction_table():
    # GB 50009-2012 表5.1.2(第1类)：m=层数 → 折减系数
    assert live_reduction_vertical(1) == 1.00
    assert live_reduction_vertical(2) == 0.85
    assert live_reduction_vertical(3) == 0.85
    assert live_reduction_vertical(4) == 0.70
    assert live_reduction_vertical(5) == 0.70
    assert live_reduction_vertical(8) == 0.65
    assert live_reduction_vertical(20) == 0.60
    assert live_reduction_vertical(21) == 0.55
    assert live_reduction_vertical(50) == 0.55


def test_vertical_reduction_monotonic():
    prev = 1.01
    for m in range(1, 30):
        v = live_reduction_vertical(m)
        assert v <= prev + 1e-9, (m, v, prev)
        prev = v


def test_beam_reduction_by_area():
    assert beam_live_reduction(10.0) == 1.0
    assert beam_live_reduction(25.0) == 1.0
    assert beam_live_reduction(26.0) == 0.9
    assert beam_live_reduction(60.0) == 0.9


def _tower(n_storeys=10):
    B = 7000
    cols = [Column(i * B, k * B, 600, 600) for i in range(3) for k in range(3)]
    beams = ([Beam(i * B, k * B, (i + 1) * B, k * B, 300, 600) for k in range(3) for i in range(2)] +
             [Beam(i * B, k * B, i * B, (k + 1) * B, 300, 600) for i in range(3) for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6.0, 3.5))  # 较大活载放大折减效果
    return Project(grid=Grid([0, B, 2 * B], [0, B, 2 * B]), floor=fl,
                   storeys=[Storey(3600, n_storeys)], seismic=Seismic(n_modes=9))


def _max_col_N(r):
    return max((mb["N"] for mb in r.members if mb["kind"] == "柱"), default=0.0)


def test_live_reduction_lowers_bottom_column_axial():
    out = os.path.join(os.path.dirname(__file__), "_lc_out")
    p = _tower(10)
    r_red = az.analyze(p, out)                 # 含折减(默认)
    N_red = _max_col_N(r_red)
    # 关闭折减(monkeypatch ψ≡1)再算
    orig = az.live_reduction_vertical
    az.live_reduction_vertical = lambda m: 1.0
    try:
        r_full = az.analyze(_tower(10), out)
        N_full = _max_col_N(r_full)
    finally:
        az.live_reduction_vertical = orig
    assert N_red < N_full, (N_red, N_full)            # 折减后底柱轴力更小
    assert N_red > 0.5 * N_full, (N_red, N_full)      # 但不至于离谱(恒载不折减)


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
