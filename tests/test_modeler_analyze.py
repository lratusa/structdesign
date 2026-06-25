import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze, ModelUnstableError


def _small():
    cols, beams = [], []
    for i in range(3):
        for k in range(3):
            cols.append(Column(i * 7000, k * 7000, 600, 600))
    for k in range(3):
        for i in range(2):
            beams.append(Beam(i * 7000, k * 7000, (i + 1) * 7000, k * 7000, 300, 600))
    for i in range(3):
        for k in range(2):
            beams.append(Beam(i * 7000, k * 7000, i * 7000, (k + 1) * 7000, 300, 600))
    fl = StandardFloor(columns=cols, beams=beams, walls=[], slab=SlabLoad(6.0, 2.5))
    return Project(grid=Grid([0, 7000, 14000], [0, 7000, 14000]), floor=fl,
                   storeys=[Storey(3600, 5)], seismic=Seismic(n_modes=9))


def test_analyze_runs_and_sane():
    r = analyze(_small(), out_dir=os.path.join(os.path.dirname(__file__), "_md_out"))
    assert r.Tx > 0 and r.T1 > 0, (r.Tx, r.T1)
    assert r.base_x > 0, r.base_x
    assert r.n_members > 0, r.n_members
    assert 0 < r.shear_weight < 1, r.shear_weight
    assert len(r.checks_table) >= 5      # 5 项规范校核(+风荷载启用时多1行基底剪力对比)
    assert r.wind_base_x > 0 and r.wind_base_y > 0, (r.wind_base_x, r.wind_base_y)
    assert r.wind_drift_x > 0, r.wind_drift_x
    assert os.path.exists(r.calcbook_md)


def test_degenerate_model_raises_clean_error():
    # 退化模型(单柱塔楼)→ 刚性楼盖该层转动质量=0 → 矩阵奇异。
    # 应抛 ModelUnstableError(带清晰提示)，而非裸 numpy LinAlgError。
    fl = StandardFloor(columns=[Column(0, 0, 600, 600)], beams=[], walls=[], slab=SlabLoad(6.0, 2.5))
    p = Project(grid=Grid([0], [0]), floor=fl, storeys=[Storey(3600, 3)], seismic=Seismic(n_modes=3))
    raised = False
    try:
        analyze(p, out_dir=os.path.join(os.path.dirname(__file__), "_md_out"))
    except ModelUnstableError as e:
        raised = True
        assert "奇异" in str(e) or "机构" in str(e), str(e)
    assert raised, "退化模型未抛 ModelUnstableError"


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
