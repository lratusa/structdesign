import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import (Column, Beam, Wall, SlabLoad, Storey, StandardFloor,
                             Seismic, Grid, Project)


def test_build_and_counts():
    fl = StandardFloor(columns=[Column(0, 0, 500, 500), Column(6000, 0, 500, 500)],
                       beams=[Beam(0, 0, 6000, 0, 300, 600)],
                       walls=[Wall(0, 0, 0, 4000, 400)], slab=SlabLoad(6.0, 2.5))
    p = Project(grid=Grid([0, 6000], [0]), floor=fl,
                storeys=[Storey(3600, 3)], seismic=Seismic())
    assert len(p.floor.columns) == 2
    assert p.total_floors() == 3
    assert p.elevations() == [0, 3600, 7200, 10800]


def test_json_roundtrip():
    fl = StandardFloor(columns=[Column(1, 2, 500, 500)], beams=[], walls=[], slab=SlabLoad())
    p = Project(grid=Grid([0], [0]), floor=fl, storeys=[Storey(3000, 2)], seismic=Seismic())
    d = p.to_dict()
    p2 = Project.from_dict(d)
    assert p2.floor.columns[0].x == 1 and p2.floor.columns[0].y == 2
    assert p2.total_floors() == 2
    assert p2.to_dict() == d


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
