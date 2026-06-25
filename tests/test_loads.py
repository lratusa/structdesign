"""
荷载组合/包络 + 能力设计调整 单元测试（手算核对）。

组合: G:M=100, Q:M=40 → 1.3·100+1.5·40 = 190 kN·m
地震: G:M=100,Q:M=40,E:M=80 → 1.3(G+0.5Q)+1.4E = 1.3·120+1.4·80 = 156+112 = 268
能力设计: 一级柱弯矩 ηc=1.7 → 100→170; 二级梁剪力 ηvb=1.2 → 150→180
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign import loads
from structdesign.loads import CaseForces, G, Q, W, E
from structdesign.codes import seismic_adjust as sa


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_basic_combo():
    cases = {G: CaseForces(M=100), Q: CaseForces(M=40)}
    env = loads.envelope(cases)
    assert approx(env.M_pos, 190.0), env.M_pos


def test_seismic_combo():
    cases = {G: CaseForces(M=100), Q: CaseForces(M=40), E: CaseForces(M=80)}
    env = loads.envelope(cases, seismic=True)
    assert approx(env.M_pos, 268.0), env.M_pos
    # 反向地震产生最负弯矩: 1.3·120 - 1.4·80 = 156-112 = 44; 但基本组合190更大为正
    assert env.M_pos >= 190.0


def test_wind_combo():
    cases = {G: CaseForces(V=50), Q: CaseForces(V=20), W: CaseForces(V=30)}
    env = loads.envelope(cases)
    # 1.3·50+1.05·20+1.5·30 = 65+21+45 = 131
    assert approx(env.V_max, 131.0), env.V_max


def test_capacity_design():
    Madj, eta = sa.column_moment_magnify(100, "一级")
    assert approx(Madj, 170.0) and approx(eta, 1.7)
    Vadj, eta = sa.beam_shear_magnify(150, "二级")
    assert approx(Vadj, 180.0) and approx(eta, 1.2)
    Vadj, eta = sa.column_shear_magnify(120, "一级")
    assert approx(Vadj, 168.0)


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
