"""平法标注与 SVG 生成测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.drawing.pingfa import BeamPingfa, beam_svg, sym


def test_symbols():
    assert sym("HPB300") == "φ"
    assert sym("HRB400") == "C"
    assert sym("HRB500") == "E"


def test_annotation_lines():
    p = BeamPingfa(beam_id="KL1", n_span=2, b=300, h=600,
                   stirrup_d=8, s_dense=100, s_normal=200, legs=2,
                   top_through="2C22", side_bars="G4C12")
    a = p.concentrated_annotation()
    assert a[0] == "KL1(2) 300×600"
    assert a[1] == "φ8@100/200(2)"
    assert a[2] == "2C22"
    assert "G4C12" in a


def test_svg_valid():
    p = BeamPingfa(beam_id="KL1", support_top="6C22", bottom="4C25", length_mm=6600)
    svg = beam_svg(p)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "6C22" in svg and "4C25" in svg
    assert "6600" in svg
    # 含上/下纵筋与箍筋元素
    assert svg.count("<line") > 5


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
