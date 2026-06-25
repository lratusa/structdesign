"""钢筋表与截面大样测试（标准表值核对）。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.detailing.schedule import bar_mass_per_m, Schedule
from structdesign.drawing.section import section_svg


def approx(a, b, tol=5e-3):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_bar_mass_table():
    # 规范钢筋理论重量表
    assert approx(bar_mass_per_m(8), 0.395, 5e-3), bar_mass_per_m(8)
    assert approx(bar_mass_per_m(20), 2.466, 5e-3), bar_mass_per_m(20)
    assert approx(bar_mass_per_m(25), 3.853, 5e-3), bar_mass_per_m(25)


def test_schedule_totals():
    sc = Schedule()
    sc.add("KL1上", "HRB400", 22, 4, 6600)   # 4D22 长6.6m
    sc.add("KL1下", "HRB400", 25, 4, 6600)
    # 4·6.6·2.984(D22) = 78.7 ; 4·6.6·3.853 = 101.7
    m22 = 4 * 6.6 * bar_mass_per_m(22)
    m25 = 4 * 6.6 * bar_mass_per_m(25)
    assert approx(sc.total_mass_kg, m22 + m25, 1e-6)
    by = sc.mass_by_diameter()
    assert approx(by[22], m22, 1e-6) and approx(by[25], m25, 1e-6)


def test_schedule_markdown():
    sc = Schedule()
    sc.add("KL1", "HRB400", 22, 4, 6600)
    md = sc.render_markdown()
    assert "D22" in md and "合计" in md


def test_section_svg():
    svg = section_svg(300, 600, n_top=4, n_bot=4, d_main=22, n_side=2)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert svg.count("<circle") >= 8        # 4上+4下纵筋 (+腰筋)
    assert "300×600" in svg


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
