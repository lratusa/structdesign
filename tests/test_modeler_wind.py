import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Grid, Project, Wind
from modeler.run.wind import mu_z, beta_z, wind_story_forces


def test_mu_z_matches_gb_table():
    # GB 50009-2012 表8.2.1 锚点（容差0.02）
    assert abs(mu_z("B", 10) - 1.00) < 0.02
    assert abs(mu_z("B", 20) - 1.23) < 0.02
    assert abs(mu_z("A", 10) - 1.28) < 0.02
    assert abs(mu_z("A", 20) - 1.52) < 0.02
    assert abs(mu_z("C", 10) - 0.65) < 0.02     # 下限
    assert abs(mu_z("C", 40) - 1.00) < 0.03
    assert abs(mu_z("D", 10) - 0.51) < 0.02     # 下限
    assert abs(mu_z("D", 60) - 0.77) < 0.03


def test_mu_z_monotonic():
    prev = 0.0
    for z in [5, 10, 20, 40, 80, 150]:
        v = mu_z("B", z)
        assert v >= prev - 1e-9, (z, v, prev)
        prev = v


def test_beta_z_threshold():
    assert beta_z(20.0, 18.0) == 1.0        # H≤30m 不计风振
    assert beta_z(60.0, 60.0) > 1.0         # H>30m 顶部放大
    assert beta_z(60.0, 60.0) > beta_z(60.0, 30.0)   # 随高度增


def _bld(nx=2, ny=1, bay=7000, storeys=None):
    cols = [Column(i * bay, k * bay, 600, 600) for i in range(nx + 1) for k in range(ny + 1)]
    fl = StandardFloor(columns=cols, slab=SlabLoad(6.0, 2.5))
    gx = [i * bay for i in range(nx + 1)]; gy = [k * bay for k in range(ny + 1)]
    return Project(grid=Grid(gx, gy), floor=fl,
                   storeys=storeys or [Storey(3600, 5)], wind=Wind(w0=0.45, terrain="B", mu_s=1.3))


def test_base_shear_is_sum_of_floor_forces():
    p = _bld()
    forces, info = wind_story_forces(p, "x")
    assert abs(info["base_shear"] - sum(forces.values())) < 1e-6
    assert len(forces) == p.total_floors()
    assert info["base_shear"] > 0


def test_floor_force_hand_check():
    # 单一楼层手算复核：F = βz·μs·μz·w0 · B · h_trib
    p = _bld(nx=2, ny=1, bay=7000, storeys=[Storey(4000, 1)])   # 单层 H=4m，B=7m
    forces, info = wind_story_forces(p, "x")
    z_mm = list(forces.keys())[0]
    z = z_mm / 1000.0
    h_trib = 4.0 / 2.0            # 单层只有下半 + 顶无上半
    expect = beta_z(4.0, z, "B") * 1.3 * mu_z("B", z) * 0.45 * 7.0 * h_trib
    assert abs(forces[z_mm] - expect) < 1e-6, (forces[z_mm], expect)


def test_direction_uses_correct_width():
    # 平面 Lx=14m(2跨) ≠ Ly=7m(1跨)：风沿X迎风宽=Ly=7，风沿Y迎风宽=Lx=14
    p = _bld(nx=2, ny=1, bay=7000)
    _, ix = wind_story_forces(p, "x")
    _, iy = wind_story_forces(p, "y")
    assert abs(ix["width"] - 7.0) < 1e-6, ix["width"]
    assert abs(iy["width"] - 14.0) < 1e-6, iy["width"]
    assert iy["base_shear"] > ix["base_shear"]    # 迎风面越宽风力越大


def test_disabled_wind_zero():
    p = _bld()
    p.wind.enabled = False
    forces, info = wind_story_forces(p, "x")
    assert forces == {} and info["base_shear"] == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
