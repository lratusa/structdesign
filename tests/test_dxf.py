"""DXF 写出器与平法 DXF 测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.drawing.dxf import DXFDoc
from structdesign.drawing.pingfa import BeamPingfa
from structdesign.drawing.pingfa_dxf import beam_dxf, batch_beams_dxf


def test_dxf_structure():
    d = DXFDoc()
    d.add_line(0, 0, 100, 0)
    d.add_text(10, 10, "KL1")
    d.add_circle(5, 5, 2)
    s = d.dumps()
    assert s.startswith("0\nSECTION")
    assert s.rstrip().endswith("EOF")
    assert "ENTITIES" in s and "LINE" in s and "TEXT" in s and "CIRCLE" in s


def test_beam_dxf_contents():
    p = BeamPingfa(beam_id="KL1", n_span=2, b=250, h=600, length_mm=6600,
                   support_top="6C22", bottom="4C25")
    s = beam_dxf(p).dumps()
    assert "LINE" in s and "TEXT" in s
    assert "6C22" in s and "4C25" in s
    # 含上下纵筋两条主线 + 多根箍筋 → LINE 数量较多
    assert s.count("LINE") > 10


def test_batch_dxf():
    beams = [BeamPingfa(beam_id=f"KL{i}", h=600, length_mm=6000,
                        support_top="4C20", bottom="3C20") for i in range(3)]
    s = batch_beams_dxf(beams).dumps()
    assert s.count("KL0") >= 1 and "KL2" in s


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
