"""3D 位移比/层间位移角测试：对称≈1，偏心>1。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.frame3d_builder import build_regular_3d
from structdesign.analysis.drift3d import displacement_ratio, story_drift_ratio


def test_symmetric_ratio_near_one():
    m = build_regular_3d(2, 2, 5, 8000, 8000, 3600, col_bh=(600, 600))
    r = displacement_ratio(m, "x")
    assert r < 1.05, r


def test_eccentric_ratio_above_one():
    # 角部大墙 → 刚心偏移 → 扭转 → 位移比>1
    m = build_regular_3d(3, 3, 5, 8000, 8000, 3600, col_bh=(600, 600),
                         wall_cols={(0, 0)}, wall_bh=(400, 5000))
    r = displacement_ratio(m, "x")
    assert r > 1.05, r


def test_story_drift_positive():
    m = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600))
    d = story_drift_ratio(m, "x", 3600, F=1e4)
    assert d > 0


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
