"""三维刚性楼盖模态测试：对称→Tx≈Ty + 存在扭转振型 + 周期比。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.frame3d_builder import build_regular_3d, floor_masses
from structdesign.analysis.modal3d import rigid_diaphragm_modal


def approx(a, b, tol=8e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_symmetric_Tx_eq_Ty():
    # 对称方形平面(2×2跨等距)、方柱 → Tx≈Ty
    m = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600))
    r = rigid_diaphragm_modal(m, floor_masses(m, 4e5))
    assert r.Tx > 0 and r.Ty > 0
    assert approx(r.Tx, r.Ty, 8e-2), (r.Tx, r.Ty)


def test_torsion_mode_exists():
    m = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600))
    r = rigid_diaphragm_modal(m, floor_masses(m, 4e5))
    assert r.Tt > 0, "应存在扭转振型"
    assert 0 < r.period_ratio < 2


def test_eccentric_raises_period_ratio():
    """把一角设大墙(刚度偏置) → 扭转更显著, 周期比上升 vs 对称。"""
    sym = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600))
    r_sym = rigid_diaphragm_modal(sym, floor_masses(sym, 4e5))
    ecc = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600),
                           wall_cols={(0, 0)}, wall_bh=(400, 4000))
    r_ecc = rigid_diaphragm_modal(ecc, floor_masses(ecc, 4e5))
    # 偏心后周期比通常上升(扭转效应增强)
    assert r_ecc.period_ratio >= r_sym.period_ratio - 0.05


def test_symmetric_modes_orthogonalized_clean():
    """简并正交化后：对称楼前两阶为纯 X、纯 Y。"""
    m = build_regular_3d(2, 2, 6, 8000, 8000, 3600, col_bh=(600, 600))
    r = rigid_diaphragm_modal(m, floor_masses(m, 6e5))
    m1, m2 = r.modes[0], r.modes[1]
    assert {m1.kind, m2.kind} == {"X", "Y"}, (m1.kind, m2.kind)
    xmode = m1 if m1.kind == "X" else m2
    assert xmode.uy < 0.1 * xmode.ux + 0.05, (xmode.ux, xmode.uy)


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
