import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.subbeam import classify_beams, secondary_transfer
from modeler.run.analyze import analyze
from structdesign import loads_takedown as td

B = 6000


def _floor_with_secondary():
    # 矩形 2B×B 四角柱 + 周边主梁 + 中间一道次梁(B,0)-(B,B)支于上下主梁中点
    cols = [Column(0, 0, 600, 600), Column(2 * B, 0, 600, 600),
            Column(0, B, 600, 600), Column(2 * B, B, 600, 600)]
    beams = [
        Beam(0, 0, 2 * B, 0, 300, 600),       # 0 下主梁
        Beam(0, B, 2 * B, B, 300, 600),       # 1 上主梁
        Beam(0, 0, 0, B, 300, 600),           # 2 左主梁
        Beam(2 * B, 0, 2 * B, B, 300, 600),   # 3 右主梁
        Beam(B, 0, B, B, 300, 600),           # 4 次梁(两端不落柱)
    ]
    return StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6.0, 2.5))


def test_classify_grid_all_primary():
    # 一键轴网式: 3×3 柱, 梁均在相邻柱间 → 全主梁
    cols = [Column(i * B, k * B, 600, 600) for i in range(3) for k in range(3)]
    beams = [Beam(i * B, k * B, (i + 1) * B, k * B, 300, 600) for k in range(3) for i in range(2)]
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    assert classify_beams(fl) == ["主"] * len(beams)


def test_classify_detects_secondary():
    fl = _floor_with_secondary()
    kinds = classify_beams(fl)
    assert kinds[:4] == ["主", "主", "主", "主"]
    assert kinds[4] == "次"


def test_secondary_transfer_point_loads():
    fl = _floor_with_secondary()
    q = td.slab_q(6.0, 2.5)                     # 11.55 kN/m²
    kinds, pls = secondary_transfer(fl, q, lambda b: 6000.0)   # 固定受荷宽 6m 便于手算
    # 次梁 L=6m, w=q*6, R=w*6/2=18q per端 → 落在 0(下主梁)和 1(上主梁)的 t=0.5
    R = q * 6.0 * 6.0 / 2.0
    assert len(pls[0]) == 1 and len(pls[1]) == 1
    assert len(pls[2]) == 0 and len(pls[3]) == 0
    for i in (0, 1):
        t, P = pls[0][0]
        assert abs(t - 0.5) < 1e-6, t
        assert abs(P - R) < 1e-6, (P, R)
    assert pls[4] == []                          # 次梁自身不接受集中力


OUT = os.path.join(os.path.dirname(__file__), "_sb_out")


def test_grid_model_no_secondary_noop():
    cols = [Column(i * B, k * B, 600, 600) for i in range(3) for k in range(3)]
    beams = ([Beam(i * B, k * B, (i + 1) * B, k * B, 300, 600) for k in range(3) for i in range(2)] +
             [Beam(i * B, k * B, i * B, (k + 1) * B, 300, 600) for i in range(3) for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    p = Project(grid=Grid([0, B, 2 * B], [0, B, 2 * B]), floor=fl,
                storeys=[Storey(3600, 3)], seismic=Seismic(n_modes=9))
    r = analyze(p, OUT)
    assert r.n_secondary == 0
    assert all(mb.get("beam_kind", "主") == "主" for mb in r.members if mb["kind"] == "梁")


def test_secondary_model_integration():
    fl = _floor_with_secondary()
    p = Project(grid=Grid([0, B, 2 * B], [0, B]), floor=fl,
                storeys=[Storey(3600, 2)], seismic=Seismic(n_modes=6))
    r = analyze(p, OUT)
    assert r.n_secondary == 1
    sec = [mb for mb in r.members if mb["kind"] == "梁" and mb.get("beam_kind") == "次"]
    assert len(sec) >= 1                         # 次梁被标记
    assert all(mb["M"] >= 0 for mb in r.members if mb["kind"] == "梁")


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
