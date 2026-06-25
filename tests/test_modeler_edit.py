import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, Wall, StandardFloor, SlabLoad
from modeler import edit


def test_move():
    c = Column(100, 200, 500, 500)
    n = edit.move_obj(c, 50, -30)
    assert (n.x, n.y) == (150, 170) and (c.x, c.y) == (100, 200)  # 原对象不变
    b = Beam(0, 0, 1000, 0)
    nb = edit.move_obj(b, 0, 500)
    assert (nb.y1, nb.y2) == (500, 500)


def test_mirror_about_y_axis():
    # 关于直线 x=1000 (竖线: (1000,0)-(1000,1000)) 镜像
    c = Column(800, 300, 500, 500)
    n = edit.mirror_obj(c, 1000, 0, 1000, 1000)
    assert abs(n.x - 1200) < 1e-6 and abs(n.y - 300) < 1e-6


def test_array():
    c = Column(0, 0, 500, 500)
    out = edit.array_objs([c], 3, 2, 6000, 6000)
    assert len(out) == 3 * 2 - 1            # 去掉原位
    xs = sorted({o.x for o in out} | {0})
    assert xs == [0, 6000, 12000]


def test_hit_and_box():
    fl = StandardFloor(columns=[Column(0, 0, 500, 500), Column(6000, 0, 500, 500)],
                       beams=[Beam(0, 0, 6000, 0, 300, 600)], walls=[], slab=SlabLoad())
    assert edit.hit_test(fl, 100, 100, 400) == ("col", 0)
    assert edit.hit_test(fl, 3000, 50, 400) == ("beam", 0)     # 点在梁线附近
    assert edit.hit_test(fl, 3000, 5000, 400) is None
    box = edit.in_box(fl, -100, -100, 6100, 100)
    assert ("col", 0) in box and ("col", 1) in box and ("beam", 0) in box


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
