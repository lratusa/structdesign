import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import (Column, Beam, Wall, WallOpening, SlabLoad, Storey,
                             StandardFloor, Seismic, Grid, Project)
from modeler import commands as cmd
from modeler.run.analyze import analyze


def test_tool_schema_is_llm_ready():
    tools = cmd.to_tool_schema()
    assert isinstance(tools, list) and tools
    for t in tools:
        assert "name" in t and "description" in t
        sch = t["input_schema"]
        assert sch["type"] == "object" and "properties" in sch and "required" in sch
    names = {t["name"] for t in tools}
    assert {"scale_openings", "set_design_rule"} <= names
    # enum 传递
    so = next(t for t in tools if t["name"] == "scale_openings")
    assert so["input_schema"]["properties"]["target"]["enum"] == ["window", "slab_opening"]


def test_unknown_command_and_missing_param():
    p = Project()
    try:
        cmd.run_command(p, "nope"); assert False
    except ValueError:
        pass
    try:
        cmd.run_command(p, "scale_openings"); assert False     # delta 必填
    except TypeError:
        pass


def test_scale_openings_from_center():
    fl = StandardFloor(walls=[Wall(0, 0, 4000, 0, 300)],
                       wall_openings=[WallOpening(1000, 0, 3000, 0, 1500, 900)])
    p = Project(floor=fl)
    msg = cmd.run_command(p, "scale_openings", delta=200, target="window")
    o = p.floor.wall_openings[0]
    width = ((o.x2 - o.x1) ** 2 + (o.y2 - o.y1) ** 2) ** 0.5
    assert abs(width - 2200) < 1e-6, width        # 2000 + 200
    assert abs(o.h - 1700) < 1e-6, o.h            # 1500 + 200
    assert abs(o.sill - 800) < 1e-6, o.sill       # 900 - 100 (中心不变)
    assert abs((o.x1 + o.x2) / 2 - 2000) < 1e-6   # 中心保持
    assert "窗洞" in msg


def test_set_design_rule_updates_policy():
    p = Project()
    cmd.run_command(p, "set_design_rule", beam_rebar_merge="envelope", prefab_joint=True)
    assert p.policy.beam_rebar_merge == "envelope"
    assert p.policy.prefab_joint is True


def _secondary_model():
    B = 6000
    cols = [Column(0, 0, 600, 600), Column(2 * B, 0, 600, 600),
            Column(0, B, 600, 600), Column(2 * B, B, 600, 600)]
    beams = [Beam(0, 0, 2 * B, 0, 300, 600), Beam(0, B, 2 * B, B, 300, 600),
             Beam(0, 0, 0, B, 300, 600), Beam(2 * B, 0, 2 * B, B, 300, 600),
             Beam(B, 0, B, B, 250, 500)]      # 次梁
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 3))
    return Project(grid=Grid([0, B, 2 * B], [0, B]), floor=fl,
                   storeys=[Storey(3600, 2)], seismic=Seismic(n_modes=6))


def test_envelope_merge_unifies_same_section_beams():
    OUT = os.path.join(os.path.dirname(__file__), "_cmd_out")
    p0 = _secondary_model()
    r0 = analyze(p0, OUT)
    bt0 = {m["bars_top"] for m in r0.members if m["kind"] == "梁" and m["sec"] == "300×600"}
    assert len(bt0) > 1, ("默认应有不同配筋", bt0)        # 受荷不同→默认配筋各异

    p1 = _secondary_model()
    cmd.run_command(p1, "set_design_rule", beam_rebar_merge="envelope")
    r1 = analyze(p1, OUT)
    grp = [m for m in r1.members if m["kind"] == "梁" and m["sec"] == "300×600"]
    bt1 = {m["bars_top"] for m in grp}
    assert len(bt1) == 1, ("取大包罗后同截面应统一", bt1)
    # 统一后的 As_top 应为组内最大(≥默认各梁)
    mx0 = max(m["As_top"] for m in r0.members if m["kind"] == "梁" and m["sec"] == "300×600")
    assert all(abs(m["As_top"] - mx0) < 1.0 for m in grp), "应取组内最大"
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


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
