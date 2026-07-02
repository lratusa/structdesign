"""重构忠实性：数据驱动的规范引擎应**复现**现有硬编码 analyze 的整体指标判定。

这证明"把规范从代码剥离成数据"是等价重构，而非改变结果。
(剪重比：数据规则用 GB 表5.2.5 按烈度取值，比原硬编码固定 1.6% 更精确；此处用 7 度使二者一致。)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from heng.bridge import heng_scan, context_from_result

OUT = os.path.join(os.path.dirname(__file__), "_heng_out")


def _model():
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 600, 600) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 700) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 700) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))   # 纯框架
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 6)],
                   seismic=Seismic(alpha_max=0.08, n_modes=9))   # 7度→剪重比与硬编码1.6%一致


def _row(result, key):
    for name, val, lim, ok in result.checks_table:
        if key in name:
            return ok
    return None


def test_engine_reproduces_hardcoded_verdicts():
    p = _model(); r = analyze(p, OUT)
    s = heng_scan(r, p, "CN")
    by = {res.rule_id: res for res in s["results"]}
    # 周期比
    assert by["CN.GB50011-2010(2016).3.4.5"].ok == _row(r, "周期比")
    # 位移比(取 X/Y 较大；硬编码分 X、Y 两行，这里比对 X)
    assert by["CN.GB50011-2010(2016).3.4.3"].ok == (_row(r, "位移比(X)") and _row(r, "位移比(Y)"))
    # 剪重比
    assert by["CN.GB50011-2010(2016).5.2.5"].ok == _row(r, "剪重比")
    # 层间位移角
    assert by["CN.GB50011-2010(2016).5.5.1"].ok == _row(r, "最大层间位移角")


def test_provenance_and_glassbox():
    p = _model(); r = analyze(p, OUT)
    s = heng_scan(r, p, "CN")
    for res in s["results"]:
        assert res.rule_id and res.provenance.get("clause")     # 每个判定可溯源到条文
        assert isinstance(res.values, dict)                     # 中间量可查(玻璃盒)
    import shutil; shutil.rmtree(OUT, ignore_errors=True)


def test_context_projection():
    p = _model(); r = analyze(p, OUT)
    ctx = context_from_result(r, p)
    assert ctx["system"] == "frame" and ctx["intensity"] == "7"
    assert "period_ratio" in ctx and "drift" in ctx
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
