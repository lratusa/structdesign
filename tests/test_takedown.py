"""荷载导算测试（守恒/解析核对）。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign import loads_takedown as td


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_one_way():
    # q=8 kN/m², 梁间距3m → w=24 kN/m
    assert approx(td.one_way_udl(8.0, 3.0), 24.0)


def test_two_way_load_conservation():
    q, lx, ly = 8.0, 4.0, 6.0
    r = td.two_way_beam_loads(q, lx, ly)
    total_beams = 2 * r.w_short * lx + 2 * r.w_long * ly
    assert approx(total_beams, q * lx * ly, 1e-9), (total_beams, q * lx * ly)
    assert approx(r.total_load, 192.0)         # 8·4·6


def test_two_way_square_panel():
    # 方板 lx=ly → 四边相同三角形, w_short=w_long=q·l/4
    q, l = 10.0, 5.0
    r = td.two_way_beam_loads(q, l, l)
    assert approx(r.w_short, q * l / 4)
    assert approx(r.w_long, q * l / 4)


def test_slab_q_combo():
    # 恒5 活2 → 1.3·5+1.5·2=9.5
    assert approx(td.slab_q(5.0, 2.0), 9.5)


def test_moment_equiv():
    r = td.two_way_beam_loads(8.0, 4.0, 6.0)
    assert approx(td.moment_equiv_triangular(r.p_peak), 2.0 / 3.0 * r.p_peak)


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
