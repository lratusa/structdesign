"""计算书规范校核章节：整体+构件级+强条自查，每条带 rule_id 条文锚点（端到端玻璃盒）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from heng.calcsection import compliance_section

OUT = os.path.join(os.path.dirname(__file__), "_cs_out")


def _model(col=600, nfloor=6):
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, col, col) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 700) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 700) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, nfloor)],
                   seismic=Seismic(alpha_max=0.08, n_modes=6))


def test_section_has_provenance_anchors():
    p = _model(); r = analyze(p, OUT)
    md = compliance_section(r, p, "CN")
    assert md.startswith("## 规范校核")
    assert "整体指标" in md and "构件级配筋校核" in md and "强制性条文自查" in md
    # 整体指标条文锚点(rule_id + 条文号)始终出现
    assert "CN.GB50011-2010(2016).3.4.5" in md          # 周期比 rule_id
    assert "5.5.1" in md and "5.2.5" in md               # 层间位移角/剪重比 条文号
    assert "依据链" in md or "溯源" in md


def test_overloaded_shows_failed_members_with_clause():
    p = _model(col=350, nfloor=15); r = analyze(p, OUT)   # 超限
    md = compliance_section(r, p, "CN")
    assert "不满足构件" in md
    # 违反条文列出 rule_id
    assert "违反条文" in md
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    import shutil; shutil.rmtree(OUT, ignore_errors=True)
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
