"""
反应谱 + 模态 + 振型分解 测试（解析解核对）。

单自由度: ω=√(k/m), T=2π√(m/k)
双自由度等质量等刚度: K=[[2,-1],[-1,1]] → λ=(3±√5)/2=2.618,0.382 → T=2π/√λ
反应谱: 平台段 α=αmax; T=1.0,αmax=0.08,Tg=0.35 → α=0.35^0.9·0.08=0.0311
阻尼ζ=0.05 → (γ,η1,η2)=(0.9,0.02,1.0)
SDOF基底剪力 = α·G = α·m·g
"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes import gb50011_spectrum as sp
from structdesign.analysis.modal import solve_shear_building
from structdesign.analysis.response_spectrum import response_spectrum_analysis


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_damping_params():
    g, e1, e2 = sp.damping_params(0.05)
    assert approx(g, 0.9) and approx(e1, 0.02) and approx(e2, 1.0)


def test_spectrum_plateau_and_descent():
    assert approx(sp.alpha(0.2, 0.08, 0.35), 0.08)         # 平台段
    expect = 0.35 ** 0.9 * 0.08
    assert approx(sp.alpha(1.0, 0.08, 0.35), expect, 1e-3)  # 曲线下降段


def test_sdof_period():
    r = solve_shear_building([100.0], [10000.0])
    assert approx(r.periods[0], 2 * math.pi * math.sqrt(100 / 10000), 1e-4)


def test_two_dof_eigen():
    r = solve_shear_building([1.0, 1.0], [1.0, 1.0])
    T1 = 2 * math.pi / math.sqrt((3 - math.sqrt(5)) / 2)  # 长周期
    T2 = 2 * math.pi / math.sqrt((3 + math.sqrt(5)) / 2)
    assert approx(r.periods[0], T1, 1e-3), r.periods
    assert approx(r.periods[1], T2, 1e-3), r.periods


def test_effective_mass_sum():
    r = solve_shear_building([1.0, 1.0, 1.0], [3.0, 2.0, 1.0])
    assert approx(sum(r.Meff), r.Mtotal, 1e-3), (sum(r.Meff), r.Mtotal)


def test_sdof_base_shear():
    res = response_spectrum_analysis([100.0], [10000.0], alpha_max=0.08, Tg=0.35, g=9.81)
    G = 100 * 9.81
    assert approx(res.base_shear, res.alphas[0] * G, 1e-6)
    assert approx(res.base_shear, 0.04726 * G, 2e-2), res.base_shear


def test_multistory_runs():
    res = response_spectrum_analysis([5e4]*5, [4e7]*5, alpha_max=0.08, Tg=0.40, g=9.81)
    assert res.base_shear > 0
    # 基底剪力应是各层剪力最大者
    assert approx(res.base_shear, max(res.story_shears), 1e-9)
    # 基底剪力不超过 αmax·总重力（粗略上界检查）
    assert res.base_shear <= 0.08 * sum(5e4*9.81 for _ in range(5)) * 1.2


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
