import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from modeler.io.dxf_import import import_drawing


def _make_dxf(path):
    doc = ezdxf.new(); msp = doc.modelspace()
    msp.add_line((0, 0), (6000, 0), dxfattribs={"layer": "WALL"})
    msp.add_line((6000, 0), (6000, 4000), dxfattribs={"layer": "WALL"})
    msp.add_circle((0, 0), 100, dxfattribs={"layer": "COL"})
    doc.saveas(path)


def test_import_dxf_lines_and_bounds():
    p = os.path.join(tempfile.gettempdir(), "_md_test.dxf"); _make_dxf(p)
    r = import_drawing(p)
    assert len(r.lines) == 2, len(r.lines)
    assert "WALL" in r.layers and "COL" in r.layers
    xmin, ymin, xmax, ymax = r.bounds
    assert xmax == 6000 and ymax == 4000
    assert len(r.snap_points()) >= 4


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
