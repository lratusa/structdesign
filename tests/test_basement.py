"""
地下室外墙 + 抗浮 测试（手算核对）。

外墙: H=3.6m, K0=0.5, γs=18, γw=10, 水位至地面, q=10kPa
  w_soil=0.5·18·3.6=32.4; w_water=10·3.6=36; w_surch=0.5·10=5 kPa
  Msoil=0.06415·32.4·3.6²=26.95; Mwater=0.06415·36·12.96=29.93; Msurch=5·12.96/8=8.10
  M=1.3(26.95+29.93)+1.5·8.10=1.3·56.88+12.15=73.94+12.15=86.10 kN·m/m
抗浮: hw=5m, A=100m², G=4000kN → Fw=10·5·100=5000; Kf=4000/5000=0.80<1.05 → 需压重
  需 ballast=1.05·5000-4000=1250 kN
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes import gb50010_basement as bm


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_wall_moment():
    M, comp = bm.basement_wall_moment(3.6, soil_unit_weight=18, water_height=3.6,
                                      surcharge=10, K0=0.5)
    assert approx(comp["w_soil_kPa"], 32.4, 1e-3), comp["w_soil_kPa"]
    assert approx(M, 86.1, 2e-2), M


def test_wall_design():
    r = bm.design_basement_wall(3.6, 300, "C30", "HRB400",
                                soil_unit_weight=18, surcharge=10)
    assert r.As_req > 0
    assert r.flexure.ok


def test_antifloat_fail():
    r = bm.anti_float_check(water_head=5.0, area=100.0, total_weight_kn=4000.0)
    assert approx(r.buoyancy, 5000.0, 1e-6)
    assert approx(r.Kf, 0.80, 1e-2)
    assert not r.ok
    assert approx(r.ballast_need, 1250.0, 1e-2), r.ballast_need


def test_antifloat_ok():
    r = bm.anti_float_check(water_head=3.0, area=100.0, total_weight_kn=4000.0)
    # Fw=3000, Kf=1.333>1.05
    assert r.ok


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
