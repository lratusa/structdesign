import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import (Column, Beam, Opening, StairPlacement, Joint, SlabLoad,
                             Storey, StandardFloor, Seismic, Grid, Project)
from modeler import edit
from modeler.run.analyze import analyze


def test_edit_openings_stairs():
    fl = StandardFloor(columns=[Column(0, 0, 500, 500)],
                       openings=[Opening(1000, 1000, 3000, 3000)],
                       stairs_placed=[StairPlacement(5000, 0, 8000, 1600, "x")])
    # 点中板洞内部 → 选板洞
    assert edit.hit_test(fl, 2000, 2000, 300) == ("open", 0)
    assert edit.hit_test(fl, 6000, 800, 300) == ("stairp", 0)
    box = edit.in_box(fl, -100, -100, 9000, 4000)
    assert ("open", 0) in box and ("stairp", 0) in box
    # 移动板洞(生成新对象不改原)
    o2 = edit.move_obj(edit.get_obj(fl, "open", 0), 100, 200)
    assert o2.x1 == 1100 and fl.openings[0].x1 == 1000


def test_analyze_excludes_opening_area():
    B = 9000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]   # 大平面，使质量不被 3e5 下限钳住
    cols = [Column(x, y, 600, 600) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    # 重载使整层质量超过 3e5 下限（否则被钳住，开洞看不出差别）
    base = StandardFloor(columns=list(cols), beams=list(beams), slab=SlabLoad(12, 4))
    holed = StandardFloor(columns=list(cols), beams=list(beams), slab=SlabLoad(12, 4),
                          openings=[Opening(0, 0, 9000, 9000)])  # 挖掉一大块
    g = Grid(xs, ys); st = [Storey(3600, 4)]; sm = Seismic(n_modes=6)
    r0 = analyze(Project(grid=g, floor=base, storeys=st, seismic=sm), "tests/_md_p1a")
    r1 = analyze(Project(grid=g, floor=holed, storeys=st, seismic=sm), "tests/_md_p1b")
    # 开洞后楼面面积减小 → 基底剪力(随质量)更小
    assert r1.base_x < r0.base_x, (r1.base_x, r0.base_x)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    import shutil
    for d in ("tests/_md_p1a", "tests/_md_p1b"):
        shutil.rmtree(d, ignore_errors=True)
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
