import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.optimize import optimize, DesignPrefs

OUT = os.path.join(os.path.dirname(__file__), "_md_opt")


def _frame(nx, ny, nz, col, dead=7.0, live=3.0):
    cols, beams = [], []
    B = 7000
    for i in range(nx + 1):
        for k in range(ny + 1):
            cols.append(Column(i * B, k * B, col, col))
    for k in range(ny + 1):
        for i in range(nx):
            beams.append(Beam(i * B, k * B, (i + 1) * B, k * B, 300, 500))
    for i in range(nx + 1):
        for k in range(ny):
            beams.append(Beam(i * B, k * B, i * B, (k + 1) * B, 300, 500))
    fl = StandardFloor(columns=cols, beams=beams, walls=[], slab=SlabLoad(dead, live))
    return Project(grid=Grid([i * B for i in range(nx + 1)], [k * B for k in range(ny + 1)]),
                   floor=fl, storeys=[Storey(3600, nz)], seismic=Seismic(n_modes=6))


def test_grow_reaches_feasible():
    # 起始 300mm 细柱、较重荷载、较高 → 应不满足 → 优化加大到满足
    p = _frame(2, 2, 6, col=300, dead=8.0, live=3.0)
    res = optimize(p, DesignPrefs(objective="稳健", strategy="grow"), OUT)
    assert res.iterations >= 2, res.iterations
    assert res.result.n_bad == 0, res.result.n_bad
    final_col = res.project.floor.columns[0].b
    assert final_col >= 300
    # 收敛后柱被加大过（起始不满足）
    assert any(h.phase == "加大" for h in res.history)


def test_economical_shrinks_oversized():
    # 起始 1200mm 超大柱 → 经济风格应能减小省料
    p = _frame(2, 2, 4, col=1200, dead=5.0, live=2.0)
    res = optimize(p, DesignPrefs(objective="经济", strategy="full"), OUT)
    final_col = res.project.floor.columns[0].b
    assert final_col < 1200, final_col
    assert res.result.n_bad == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc()
            print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
