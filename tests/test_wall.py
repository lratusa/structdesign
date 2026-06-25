"""
墙肢生长单元测试 —— 与手算核对。

轴压比限值(二级)=0.6, C40 fc=19.1。required lw = N/(0.6·fc·bw)。

T1 可生长可行: bw=200,N=5000kN → 需lw=5e6/(0.6·19.1·200)=2181.5→取2200
   μ(2200)=5e6/(19.1·200·2200)=0.5950 ≤0.6 ✓
T2 无解→建筑配合: 同上但 lw_max=2000 → clamp2000, μ=0.6545>0.6 → arch_request
T3 无需生长: bw=300,N=2000kN,lw_init=1500 → 需lw=581.7<1500, μ=0.2327 ✓
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.arch import WallEnvelope
from structdesign.codes import gb50010_wall as gw
from structdesign.design_wall import design_wall_pier


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_required_lw():
    lw = gw.required_lw_for_axial(5000, 200, "C40", "二级")
    assert approx(lw, 2181.5, 1e-3), lw


def test_growth_feasible():
    env = WallEnvelope("W1", axis="2/B", lw_min=200, lw_max=2500,
                       thickness_options=[200])
    r = design_wall_pier("W1", 5000, 300, 200, env, "C40", "HRB400", "二级")
    assert r.feasible
    assert approx(r.lw_final, 2200, 1e-2), r.lw_final
    assert r.mu_N <= 0.6 + 1e-6, r.mu_N
    assert r.reinforcement is not None


def test_growth_infeasible_arch_request():
    env = WallEnvelope("W2", axis="2/B", lw_min=200, lw_max=2000,
                       thickness_options=[200])
    r = design_wall_pier("W2", 5000, 300, 200, env, "C40", "HRB400", "二级")
    assert not r.feasible
    assert r.arch_request != ""
    assert "填充墙让位" in r.arch_request


def test_no_growth_needed():
    env = WallEnvelope("W3", axis="3/C", lw_min=200, lw_max=2500,
                       thickness_options=[300])
    r = design_wall_pier("W3", 2000, 150, 120, env, "C40", "HRB400", "二级",
                         lw_init=1500)
    assert r.feasible
    assert approx(r.lw_final, 1500, 1e-6), r.lw_final
    assert approx(r.mu_N, 0.2327, 3e-2), r.mu_N


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
