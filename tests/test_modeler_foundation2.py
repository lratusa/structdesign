import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, Wall, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from modeler.run.foundation import (design_strip_footings, design_raft, recommend_foundation,
                                     design_piles)

OUT = os.path.join(os.path.dirname(__file__), "_fdn2_out")
B = 7000


def _model(walls=True, n=6):
    xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 500, 500) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)] +
             [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    wl = [Wall(B, B, 2 * B, B, 300)] if walls else []
    fl = StandardFloor(columns=cols, beams=beams, walls=wl, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, n)], seismic=Seismic(n_modes=6))


def test_strip_footing_bearing():
    p = _model(walls=True)
    r = analyze(p, OUT)
    strips, rows = design_strip_footings(p, r, fak=200.0)
    assert strips, "应有墙下条基"
    for s in strips:
        # 底宽满足承载力：B·fak ≥ 线荷载特征值
        assert s["B"] * 200.0 >= s["Nk_per_m"] - 1e-6, (s["B"], s["Nk_per_m"])
        assert s["h"] >= 0.30 and s["B"] >= 0.8
    assert rows and rows[0][0].startswith("TJ")


def test_strip_width_grows_with_load():
    s_low = design_strip_footings(_model(walls=True, n=3),
                                  analyze(_model(walls=True, n=3), OUT), fak=200.0)[0]
    s_high = design_strip_footings(_model(walls=True, n=12),
                                   analyze(_model(walls=True, n=12), OUT), fak=200.0)[0]
    assert s_high[0]["B"] >= s_low[0]["B"], (s_high[0]["B"], s_low[0]["B"])


def test_raft_pressure_check():
    p = _model(walls=False, n=6)
    r = analyze(p, OUT)
    raft = design_raft(p, r, fak=200.0)
    assert raft["p_avg"] > 0 and raft["t"] >= 0.30
    # ok 标志与压力-承载力一致
    assert raft["ok"] == (raft["p_avg"] <= raft["fak"])
    # 平均反力 = 总轴力/筏板面积(量级核对)
    assert raft["Nk_total"] > 0


def test_raft_overload_flagged():
    # 很多层 → 平均反力可能超 fak（小 fak） → ok=False
    p = _model(walls=False, n=20)
    r = analyze(p, OUT)
    raft = design_raft(p, r, fak=100.0)
    assert raft["ok"] == (raft["p_avg"] <= 100.0)


def test_recommend_foundation():
    rw = recommend_foundation(_model(walls=True, n=6), analyze(_model(walls=True, n=6), OUT), fak=200.0)
    assert "条" in rw["kind"] or "筏" in rw["kind"]      # 含墙 → 条基或筏板
    rn = recommend_foundation(_model(walls=False, n=3), analyze(_model(walls=False, n=3), OUT), fak=300.0)
    assert "ratio" in rn and 0 <= rn["ratio"] <= 5


def test_pile_count_covers_load():
    p = _model(walls=False, n=10)
    r = analyze(p, OUT)
    caps, rows = design_piles(p, r, Ra=1200.0)
    assert caps, "应有承台"
    for c in caps.values():
        assert c["n"] * 1200.0 >= c["Nk"] - 1e-6, (c["n"], c["Nk"])   # 桩数×单桩承载≥轴力
        assert c["cap"] >= 800
    assert rows[0][0].startswith("CT")


def test_pile_count_grows_with_load():
    def maxn(nfl):
        p = _model(walls=False, n=nfl)
        caps, _ = design_piles(p, analyze(p, OUT), Ra=800.0)
        return max(c["n"] for c in caps.values())
    assert maxn(15) >= maxn(3)


def teardown_module(mod):
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
