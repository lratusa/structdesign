import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, StandardFloor, Storey, Grid, Project
from modeler.run.checks import continuity_check, auto_transfer

B = 8000


def _floor(pts):
    return StandardFloor(columns=[Column(x, y, 600, 600) for (x, y) in pts])


def test_aligned_no_issue():
    # 大底盘: 裙房4柱(角) + 塔楼是其子集(2柱) → 对齐, 无悬空
    podium = _floor([(0, 0), (B, 0), (0, B), (B, B)])
    tower = _floor([(0, 0), (B, 0)])
    p = Project(grid=Grid([0, B], [0, B]), floor=podium, floors={"T": tower},
                storeys=[Storey(4000, 2, ""), Storey(3300, 3, "T")])
    assert continuity_check(p) == []


def test_unsupported_detected():
    # 上层有一柱(2B,0)在下层不存在 → 悬空, 应检出
    lower = _floor([(0, 0), (B, 0)])
    upper = _floor([(0, 0), (B, 0), (2 * B, 0)])
    p = Project(grid=Grid([0, B, 2 * B], [0]), floor=lower, floors={"U": upper},
                storeys=[Storey(4000, 1, ""), Storey(3300, 1, "U")])
    issues = continuity_check(p)
    assert len(issues) == 1, issues
    assert issues[0]["level"] == 2 and abs(issues[0]["x"] - 2 * B) < 1


def test_single_floor_no_issue():
    p = Project(grid=Grid([0, B], [0]), floor=_floor([(0, 0), (B, 0)]),
                storeys=[Storey(3600, 5)])
    assert continuity_check(p) == []


def test_auto_transfer():
    # 下层两柱(0,0)(2B,0)；上层在中点(B,0)有悬空柱 → 应在下层加一道转换梁(两段)
    lower = _floor([(0, 0), (2 * B, 0)])
    upper = _floor([(B, 0)])
    p = Project(grid=Grid([0, B, 2 * B], [0]), floor=lower, floors={"U": upper},
                storeys=[Storey(4500, 1, ""), Storey(3300, 1, "U")])
    n0 = len(lower.beams)
    added = auto_transfer(p)
    assert len(added) == 1, added
    assert len(lower.beams) == n0 + 2          # 两段转换梁(在悬空点相交)
    assert lower.beams[-1].h >= 700            # 深梁
    # 加转换梁后, 悬空点处下层多了梁端节点(支承上柱)
    pts = {(round(b.x1), round(b.y1)) for b in lower.beams} | {(round(b.x2), round(b.y2)) for b in lower.beams}
    assert (B, 0) in pts


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
