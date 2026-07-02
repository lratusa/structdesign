"""构件级配筋校核纳入规范引擎：逐柱/墙/梁跑规则，每条判定带条文出处（玻璃盒到构件层）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, Wall, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from heng.bridge import member_scan, member_check, member_context

OUT = os.path.join(os.path.dirname(__file__), "_mbr_out")


def _model(col=600, nfloor=6, wall=False):
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, col, col) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 700) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 700) for x in xs for k in range(2)])
    w = [Wall(B, B, 2 * B, B, 300)] if wall else []
    fl = StandardFloor(columns=cols, beams=beams, walls=w, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, nfloor)],
                   seismic=Seismic(alpha_max=0.08, n_modes=6))


def test_column_rules_with_provenance():
    p = _model(); r = analyze(p, OUT)
    col = next(m for m in r.members if m["kind"] == "柱")
    chk = member_check(col, p)
    ids = {res.rule_id for res in chk["results"]}
    # 柱应跑：轴压比6.3.6、最小配筋率6.3.7、最大配筋率9.3.1
    assert "CN.GB50011-2010(2016).6.3.6" in ids
    assert "CN.GB50011-2010(2016).6.3.7" in ids
    assert "CN.GB50010-2010(2015).9.3.1" in ids
    for res in chk["results"]:
        assert res.provenance.get("clause") and res.values     # 逐条溯源+中间量


def test_beam_min_reinforcement_runs():
    p = _model(); r = analyze(p, OUT)
    beam = next(m for m in r.members if m["kind"] == "梁")
    chk = member_check(beam, p)
    ids = {res.rule_id for res in chk["results"]}
    assert "CN.GB50010-2010(2015).8.5.1" in ids                # 梁最小配筋率入引擎


def test_wall_axial_ratio_runs():
    p = _model(wall=True); r = analyze(p, OUT)
    walls = [m for m in r.members if m["kind"] == "墙"]
    if walls:
        chk = member_check(walls[0], p)
        ids = {res.rule_id for res in chk["results"]}
        assert "CN.GB50011-2010(2016).6.4.2" in ids            # 墙轴压比入引擎


def test_full_member_scan_wellsized_all_ok():
    p = _model(col=600, nfloor=6); r = analyze(p, OUT)
    s = member_scan(r, p)
    assert s["n_checks"] > 0
    assert s["all_ok"] is True                                 # 合理截面→构件级全过


def test_overloaded_column_flagged():
    p = _model(col=350, nfloor=15); r = analyze(p, OUT)        # 小柱高层→轴压比超限
    s = member_scan(r, p)
    assert s["failed"], "超限柱应被构件级引擎标出"
    # 失败原因可溯源到具体条文
    fr = s["failed"][0]
    bad = [res for res in fr["results"] if not res.ok]
    assert bad and bad[0].provenance.get("clause")
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
