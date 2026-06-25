"""
GB 50010 梁内核单元测试 — 与手算核对。

手算算例（与代码独立）：
  截面 b=250, h=500, C30(fc=14.3, ft=1.43), HRB400(fy=360, ξb=0.518),
  a_s=40 → h0=460。
受弯 M=150 kN·m:
  αs = 150e6/(1.0·14.3·250·460²) = 0.19829
  ξ  = 1-√(1-2·0.19829) = 0.22320  (<0.518 单筋)
  x  = 0.22320·460 = 102.67 mm
  As = 1.0·14.3·250·102.67/360 = 1019.6 mm²
受剪 V=180 kN（箍筋 HPB300，受剪用 fyv=270）:
  Vmax = 0.25·1·14.3·250·460 = 411125 N = 411.1 kN  (>180 OK)
  Vc   = 0.7·1.43·250·460 = 115115 N = 115.1 kN  (<180 需箍筋)
  Asv/s = (180000-115115)/(270·460) = 0.52243 mm²/mm
最小配筋率: ρmin=max(0.2%,0.45·1.43/360=0.1788%)=0.2% → As,min=0.002·250·500=250 mm²
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes import gb50010_beam as gb


def approx(a, b, tol=1e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_flexure_singly():
    r = gb.design_flexure(250, 500, 150, "C30", "HRB400", a_s=40)
    assert r.ok
    assert not r.doubly
    assert approx(r.xi, 0.22320, 1e-3), r.xi
    assert approx(r.As, 1019.6, 1e-2), r.As


def test_flexure_doubly_triggered():
    # M=320 → αs=0.423(<0.5), ξ=0.608>ξb=0.518，应转双筋
    r = gb.design_flexure(250, 500, 320, "C30", "HRB400", a_s=40, a_s_prime=40)
    assert r.doubly
    assert r.As_comp > 0


def test_min_reinforcement():
    As_min, rho = gb.min_tension_area(250, 500, "C30", "HRB400")
    assert approx(rho, 0.002, 1e-6), rho
    assert approx(As_min, 250.0, 1e-6), As_min


def test_shear_section_limit_and_stirrups():
    r = gb.design_shear(250, 500, 180, "C30", "HPB300", a_s=40)
    assert r.section_ok
    assert not r.only_constructional
    assert approx(r.Asv_s, 0.52243, 1e-3), r.Asv_s


def test_shear_constructional_only():
    # 小剪力 V < Vc(=115kN) → 仅构造
    r = gb.design_shear(250, 500, 90, "C30", "HPB300", a_s=40)
    assert r.only_constructional


def test_shear_section_overlimit():
    # 极大剪力触发剪压比超限
    r = gb.design_shear(250, 500, 600, "C30", "HPB300", a_s=40)
    assert not r.section_ok
    assert not r.ok


def test_alpha1_beta1():
    import structdesign.materials as m
    c30 = m.concrete("C30")
    assert approx(c30.alpha1, 1.0, 1e-9)
    assert approx(c30.beta1, 0.8, 1e-9)
    c60 = m.concrete("C60")
    assert c60.alpha1 < 1.0 and c60.beta1 < 0.8


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
