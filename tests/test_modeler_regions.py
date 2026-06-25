import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import (Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project)
from modeler import regions
from modeler import commands as cmd


def test_registry_has_national_and_beijing():
    keys = {r.key for r in regions.list_regions()}
    assert {"national", "beijing"} <= keys
    bj = regions.get_region("beijing")
    assert "DBJ 11-501" in " ".join(bj.codes)        # 北京地基地标
    assert bj.codes[:4] == regions.GB_CODES           # 国标为基线


def test_apply_beijing_fills_params():
    p = Project()
    msg = regions.apply_region(p, "beijing")
    assert p.region == "beijing"
    assert abs(p.seismic.alpha_max - 0.16) < 1e-9      # 8度多遇
    assert abs(p.seismic.Tg - 0.40) < 1e-9             # II类场地第二组
    assert abs(p.wind.w0 - 0.45) < 1e-9                # 北京基本风压
    assert p.wind.terrain == "C"
    assert "北京" in msg


def test_apply_national_default():
    p = Project()
    regions.apply_region(p, "national")
    assert p.region == "national"
    assert regions.get_region("national").codes == regions.GB_CODES


def test_set_region_command():
    p = Project()
    cmd.run_command(p, "set_region", region="beijing")
    assert p.region == "beijing" and abs(p.wind.w0 - 0.45) < 1e-9
    # 命令在 LLM 工具列表中
    names = {t["name"] for t in cmd.to_tool_schema()}
    assert "set_region" in names


def test_calcbook_cites_region_codes():
    B = 7000
    cols = [Column(i * B, k * B, 500, 500) for i in range(3) for k in range(3)]
    beams = ([Beam(i * B, k * B, (i + 1) * B, k * B, 300, 600) for k in range(3) for i in range(2)] +
             [Beam(i * B, k * B, i * B, (k + 1) * B, 300, 600) for i in range(3) for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    p = Project(grid=Grid([0, B, 2 * B], [0, B, 2 * B]), floor=fl,
                storeys=[Storey(3600, 3)], seismic=Seismic(n_modes=9))
    regions.apply_region(p, "beijing")
    from modeler.run.analyze import analyze
    OUT = os.path.join(os.path.dirname(__file__), "_rg_out")
    r = analyze(p, OUT)
    md = open(r.calcbook_md, encoding="utf-8").read()
    assert "DBJ 11-501" in md, "计算书应引用北京地标"
    assert "北京" in md
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


def test_region_roundtrip():
    p = Project(); regions.apply_region(p, "beijing")
    p2 = Project.from_dict(p.to_dict())
    assert p2.region == "beijing"


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
