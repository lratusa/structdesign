import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze


def _bld(alpha=0.16, vertical=False):
    B = 7000
    cols = [Column(i * B, k * B, 600, 600) for i in range(3) for k in range(3)]
    beams = ([Beam(i * B, k * B, (i + 1) * B, k * B, 300, 600) for k in range(3) for i in range(2)] +
             [Beam(i * B, k * B, i * B, (k + 1) * B, 300, 600) for i in range(3) for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6.0, 2.5))
    return Project(grid=Grid([0, B, 2 * B], [0, B, 2 * B]), floor=fl,
                   storeys=[Storey(3600, 5)],
                   seismic=Seismic(alpha_max=alpha, n_modes=9, vertical=vertical))


def _max_col_N(r):
    return max((mb["N"] for mb in r.members if mb["kind"] == "柱"), default=0.0)


OUT = os.path.join(os.path.dirname(__file__), "_vs_out")


def test_vertical_disabled_zero():
    r = analyze(_bld(vertical=False), OUT)
    assert r.vert_on is False
    assert r.vert_Evk == 0.0 and r.vert_col_N == 0.0


def test_vertical_enabled_adds_axial():
    r_off = analyze(_bld(vertical=False), OUT)
    r_on = analyze(_bld(vertical=True), OUT)
    assert r_on.vert_on is True
    assert r_on.vert_Evk > 0.0
    assert r_on.vert_col_N > 0.0
    assert _max_col_N(r_on) > _max_col_N(r_off)        # 柱轴力因竖向地震增大


def test_vertical_Evk_scales_with_alpha():
    r1 = analyze(_bld(alpha=0.16, vertical=True), OUT)
    r2 = analyze(_bld(alpha=0.32, vertical=True), OUT)
    # F_Evk ∝ α_max → 翻倍
    assert abs(r2.vert_Evk - 2 * r1.vert_Evk) < 1e-6 * r2.vert_Evk, (r1.vert_Evk, r2.vert_Evk)
    assert abs(r2.vert_col_N - 2 * r1.vert_col_N) < 0.05 * r2.vert_col_N, (r1.vert_col_N, r2.vert_col_N)


def test_vertical_Evk_magnitude_reasonable():
    # F_Evk = 0.65·α_max·0.75·ΣG_rep；ΣG_rep≈(dead+0.5live)·面积·层数
    r = analyze(_bld(alpha=0.20, vertical=True), OUT)
    area = 14.0 * 14.0          # 2×2 跨, 7m → 14m 见方
    G_rep = (6.0 + 0.5 * 2.5) * area * 5 * 1e3   # N
    expect = 0.65 * 0.20 * 0.75 * G_rep
    assert 0.7 * expect < r.vert_Evk < 1.3 * expect, (r.vert_Evk, expect)


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
