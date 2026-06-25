"""3D 轴测可视化 SVG 测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.frame3d_builder import build_regular_3d
from structdesign.drawing.iso3d import model_svg


def test_svg_valid():
    m = build_regular_3d(2, 2, 4, 8000, 8000, 3600, col_bh=(600, 600),
                         wall_cols={(1, 1)}, wall_bh=(400, 3000))
    svg = model_svg(m, title="t")
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    # 杆件数 = 柱 + 梁X + 梁Y
    assert svg.count("<line") >= len(m.members)
    assert "#b00" in svg   # 含墙(红色)


def test_deformed_differs():
    m = build_regular_3d(2, 2, 4, 8000, 8000, 3600)
    base = model_svg(m)
    defo = {nid: [50.0, 0, 0] for nid in m.nodes}   # 整体X位移
    moved = model_svg(m, deformed=defo, mag=10)
    assert base != moved
    assert "变形放大" in moved


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
