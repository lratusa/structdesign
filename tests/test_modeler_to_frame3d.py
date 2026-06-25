import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.build.to_frame3d import build_frame3d
from structdesign.frame3d_builder import build_regular_3d, floor_masses
from structdesign.analysis.modal3d import rigid_diaphragm_modal


def _regular_via_model(nx, ny, nz, bx, by, hz, cb=(600, 600), bb=(300, 600)):
    cols, beams = [], []
    for i in range(nx + 1):
        for k in range(ny + 1):
            cols.append(Column(i * bx, k * by, cb[0], cb[1]))
    for k in range(ny + 1):
        for i in range(nx):
            beams.append(Beam(i * bx, k * by, (i + 1) * bx, k * by, bb[0], bb[1]))
    for i in range(nx + 1):
        for k in range(ny):
            beams.append(Beam(i * bx, k * by, i * bx, (k + 1) * by, bb[0], bb[1]))
    fl = StandardFloor(columns=cols, beams=beams, walls=[], slab=SlabLoad())
    return Project(grid=Grid([i * bx for i in range(nx + 1)], [k * by for k in range(ny + 1)]),
                   floor=fl, storeys=[Storey(hz, nz)], seismic=Seismic())


def test_node_member_counts_match():
    nx, ny, nz, bx, by, hz = 3, 3, 4, 8000, 8000, 3600
    ref = build_regular_3d(nx, ny, nz, bx, by, hz, col_bh=(600, 600), beam_bh=(300, 600))
    got = build_frame3d(_regular_via_model(nx, ny, nz, bx, by, hz))
    assert len(got.nodes) == len(ref.nodes), (len(got.nodes), len(ref.nodes))
    assert len(got.members) == len(ref.members), (len(got.members), len(ref.members))


def test_first_period_matches():
    nx, ny, nz, bx, by, hz = 3, 3, 4, 8000, 8000, 3600
    ref = build_regular_3d(nx, ny, nz, bx, by, hz, col_bh=(600, 600), beam_bh=(300, 600))
    got = build_frame3d(_regular_via_model(nx, ny, nz, bx, by, hz))
    mass = 6e5
    Tr = rigid_diaphragm_modal(ref, floor_masses(ref, mass)).T1
    Tg = rigid_diaphragm_modal(got, floor_masses(got, mass)).T1
    assert abs(Tr - Tg) / Tr < 0.02, (Tr, Tg)


def test_wall_adds_stiffness():
    # 同框架加一道墙 → 周期应下降（更刚）
    from modeler.project import Wall
    base = _regular_via_model(2, 2, 5, 8000, 8000, 3600)
    walled = _regular_via_model(2, 2, 5, 8000, 8000, 3600)
    walled.floor.walls = [Wall(8000, 0, 8000, 8000, 400)]
    mass = 6e5
    Tb = rigid_diaphragm_modal(build_frame3d(base), floor_masses(build_frame3d(base), mass)).T1
    mw = build_frame3d(walled)
    Tw = rigid_diaphragm_modal(mw, floor_masses(mw, mass)).T1
    assert Tw < Tb, (Tb, Tw)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
