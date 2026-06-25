"""
柱内核单元测试 —— 与手算核对。

大偏心算例：b=h=400, C30(fc=14.3,α1=1), HRB400(fy=fyc=360,ξb=0.518), a_s=40,h0=360
  N=600kN, M=200kN·m
  e0=200e6/600e3=333.3; ea=max(20,400/30)=20; ei=353.3; e=353.3+200-40=513.3mm
  x=N/(α1fc·b)=600000/(14.3·400)=104.9mm; ξ=0.291<0.518 → 大偏心
  x>2a_s'=80: As=As'=(N·e-α1fc·b·x(h0-x/2))/(fyc(h0-a_s'))
    N·e=600000·513.3=3.080e8
    α1fc·b·x(h0-x/2)=14.3·400·104.9·(360-52.45)=1.845e8
    As=(3.080e8-1.845e8)/(360·320)=1072 mm²
轴压比：μ=600000/(14.3·160000)=0.262
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes import gb50010_column as gc


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_large_eccentric():
    r = gc.design_column_symmetric(400, 400, 600, 200, "C30", "HRB400", a_s=40)
    assert r.eccentric == "大偏心", r.eccentric
    assert approx(r.As_each, 1072, 3e-2), r.As_each


def test_small_eccentric():
    # 大轴力小弯矩 → 小偏心
    r = gc.design_column_symmetric(500, 500, 4000, 80, "C40", "HRB400", a_s=40)
    assert r.eccentric == "小偏心", r.eccentric
    assert r.As_each >= 0


def test_axial_ratio():
    mu, limit, ok = gc.axial_compression_ratio(600, 400, 400, "C30", "二级")
    assert approx(mu, 0.262, 2e-2), mu
    assert limit == 0.75
    assert ok


def test_axial_ratio_overlimit():
    mu, limit, ok = gc.axial_compression_ratio(3000, 400, 400, "C30", "一级")
    # μ=3e6/(14.3·160000)=1.31 > 0.65
    assert not ok


def test_min_reinforcement():
    As_min, rho = gc.column_min_reinforcement(400, 400, "二级")
    assert approx(rho, 0.007, 1e-6)
    assert approx(As_min, 0.007 * 400 * 400, 1e-6)


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
