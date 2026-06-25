import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt5 import QtWidgets, QtGui
from modeler.app import MainWindow
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project


def test_window_constructs_and_renders():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    w = MainWindow(); w.resize(1000, 700)
    cols = [Column(i * 6000, k * 6000, 500, 500) for i in range(3) for k in range(3)]
    beams = []
    xs = [0, 6000, 12000]
    for y in xs:
        for i in range(2):
            beams.append(Beam(xs[i], y, xs[i + 1], y, 300, 600))
    w.project = Project(grid=Grid(xs, xs),
                        floor=StandardFloor(columns=cols, beams=beams, walls=[], slab=SlabLoad()),
                        storeys=[Storey(3600, 3)], seismic=Seismic())
    w._refresh(); w.canvas.fit()
    pix = QtGui.QPixmap(w.size()); w.render(pix)
    out = os.path.join(os.path.dirname(__file__), "_md_smoke.png"); pix.save(out)
    assert os.path.exists(out) and os.path.getsize(out) > 1000


if __name__ == "__main__":
    try:
        test_window_constructs_and_renders()
        print("PASS smoke"); sys.exit(0)
    except Exception as e:
        import traceback; traceback.print_exc()
        print("FAIL smoke", repr(e)); sys.exit(1)
