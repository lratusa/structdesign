"""三维振型分解反应谱(逐振型→CQC)测试。

注：用非对称(矩形)平面避免简并振型(完全对称时 Tx=Ty 简并，X/Y 振型为任意线性
组合，是已知数值难点)。真实建筑罕有完全对称。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.frame3d_builder import build_regular_3d, floor_masses
from structdesign.analysis.rspectrum3d import response_spectrum_3d


def _build():
    return build_regular_3d(3, 2, 6, 8000, 7000, 3600, col_bh=(600, 600),
                            wall_cols={(1, 1)}, wall_bh=(400, 3000))


def test_runs_base_shear_sane():
    m = _build()
    res = response_spectrum_3d(m, floor_masses(m, 5e5), 0.16, 0.40, n_modes=12)
    W = 6 * 5e5 * 9.81
    assert res["base_x"] > 0 and res["base_y"] > 0
    swr = res["base_x"] / W
    assert 0.02 <= swr <= 0.15, swr


def test_member_biaxial_forces():
    m = _build()
    res = response_spectrum_3d(m, floor_masses(m, 5e5), 0.16, 0.40, n_modes=9)
    mf = res["member_forces"]
    cols = [k for k in mf if k.startswith("Z") and k.endswith("_1")]
    assert any(mf[k]["My"] > 0 and mf[k]["Mz"] > 0 for k in cols)
    assert len(mf) == len(m.members)


def test_bidirectional_combination_applied():
    m = _build()
    res = response_spectrum_3d(m, floor_masses(m, 5e5), 0.16, 0.40, n_modes=9)
    assert res["base_bi"] >= max(res["base_x"], res["base_y"]) - 1e-6


def test_symmetric_base_shear_balanced():
    """简并正交化后：完全对称楼 Vx≈Vy（此前因简并振型相差约一倍）。"""
    from structdesign.frame3d_builder import build_regular_3d
    m = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600))
    res = response_spectrum_3d(m, floor_masses(m, 6e5), 0.16, 0.40, n_modes=18)
    rel = abs(res["base_x"] - res["base_y"]) / res["base_x"]
    assert rel < 0.12, rel


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
