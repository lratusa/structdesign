import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5 import QtWidgets
from modeler.app import MainWindow
from modeler.project import Column, Grid, StandardFloor, SlabLoad

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def _win():
    w = MainWindow()
    w.project.floor = StandardFloor(columns=[Column(0, 0, 500, 500), Column(6000, 0, 500, 500)],
                                    beams=[], walls=[], slab=SlabLoad())
    w.project.grid = Grid([0, 6000], [0])
    w.selected = set(); w._undo = []; w._redo = []
    return w


def _do_op(w, kind, p0, p1):
    w._start_op(kind)
    w._on_pick(*p0); w._on_pick(*p1)


def test_copy_and_undo():
    w = _win()
    w.selected = {("col", 0), ("col", 1)}
    _do_op(w, "copy", (0, 0), (0, 8000))           # 向上复制 8m
    assert len(w.project.floor.columns) == 4, len(w.project.floor.columns)
    w._undo_do()
    assert len(w.project.floor.columns) == 2
    w._redo_do()
    assert len(w.project.floor.columns) == 4


def test_move():
    w = _win()
    w.selected = {("col", 0)}
    _do_op(w, "move", (0, 0), (1000, 2000))
    c = w.project.floor.columns[0]
    assert (c.x, c.y) == (1000, 2000), (c.x, c.y)


def test_mirror():
    w = _win()
    w.selected = {("col", 0)}                       # (0,0)
    _do_op(w, "mirror", (3000, -1000), (3000, 1000))   # 关于 x=3000 镜像
    xs = sorted(c.x for c in w.project.floor.columns)
    assert 6000 in xs and any(abs(x - 6000) < 1 for x in xs)  # 出现镜像点 x=6000
    assert len(w.project.floor.columns) == 3


def test_box_select_and_delete():
    w = _win()
    w._on_box_select(-100, -100, 7000, 100)         # 框选两柱
    assert len(w.selected) == 2
    w._delete_selected()
    assert len(w.project.floor.columns) == 0
    w._undo_do()
    assert len(w.project.floor.columns) == 2


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
