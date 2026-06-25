"""CQC 振型组合验证（解析极限）。"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes.cqc import correlation, cqc, srss


def approx(a, b, tol=1e-3):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_self_correlation_one():
    assert approx(correlation(1.0, 1.0), 1.0)


def test_separated_modes_to_zero():
    # 周期相差很大 → 相关系数趋近 0
    assert correlation(1.0, 0.1) < 0.02


def test_close_modes_high_corr():
    # 周期接近 → 相关系数大
    assert correlation(1.0, 0.97) > 0.5


def test_cqc_separated_equals_srss():
    vals = [10.0, 6.0]
    Ts = [1.0, 0.2]                 # 分离
    assert approx(cqc(vals, Ts), srss(vals), 2e-2)


def test_cqc_identical_periods_sum():
    # 完全相关(同周期, 同号) → CQC = 代数和 > SRSS
    vals = [10.0, 6.0]
    Ts = [1.0, 1.0]
    assert approx(cqc(vals, Ts), 16.0, 1e-6)
    assert cqc(vals, Ts) > srss(vals)


def test_cqc_single():
    assert approx(cqc([7.0], [1.0]), 7.0)


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
