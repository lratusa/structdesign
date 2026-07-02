"""单一结构数据模型贯穿全过程（设计书 §2.2 护城河② / §8 全过程工作流）的完整性守护。

护城河②："单一结构数据模型贯穿方案到运维"。本测试证明：一个模型经
  Project → SSM → 分析(analyze) → 整体校核(heng_scan) → 构件校核(member_scan)
         → 计算书章节(compliance_section) → 送审审查包(review_package)
全链路**同源一致**——构件数在各阶段恒等、审查包引用的规范集与辖区解析一致、
不发生"重新建模/数据分叉"。这是把方案层到交付层用一个语义模型串起来的可回归证据。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from modeler.run.analyze import analyze
from heng.ssm import ssm_from_project
from heng.bridge import heng_scan, member_scan
from heng.calcsection import compliance_section
from heng.review import review_package
from heng.codes.jurisdiction import resolve

OUT = os.path.join(os.path.dirname(__file__), "_wf_out")


def _model():
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 600, 600) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 700) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 700) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 6)],
                   seismic=Seismic(alpha_max=0.08, n_modes=6))


def test_single_model_flows_through_all_stages():
    p = _model()
    # 一个模型 → 各阶段
    ssm = ssm_from_project(p, "CN")
    r = analyze(p, OUT)
    scan = heng_scan(r, p, "CN")
    ms = member_scan(r, p, "CN")
    cs = compliance_section(r, p, "CN")
    pkg = review_package(r, p, "CN")

    fl = p.floor
    # ① SSM 无损投影楼层语义模型(不丢不增)——方案层单一数据源
    n_ssm = ssm["meta"]["n_members"]
    assert n_ssm == len(fl.columns) + len(fl.beams) + len(fl.walls), \
        f"SSM({n_ssm}) 未无损投影楼层模型({len(fl.columns)+len(fl.beams)+len(fl.walls)})"
    # ② 审查包与 SSM 同源(送审快照就是同一投影，构件数恒等)
    assert pkg["n_members"] == n_ssm, f"审查包({pkg['n_members']}) 与 SSM({n_ssm}) 分叉"
    # ③ 校核层与分析层 1:1(构件校核不丢不增分析产出的构件)
    assert len(ms["members"]) == len(r.members), \
        f"构件校核({len(ms['members'])}) 与分析构件({len(r.members)}) 分叉"

    # ④ 辖区/规范集同源：审查包规范集 == 辖区解析器直接产出
    assert pkg["codes"] == resolve("CN", "building", "design").codes, "审查包规范集与辖区解析分叉"
    assert pkg["jurisdiction"] == "CN"

    # ⑤ 计算书章节与整体扫描同源：扫描到的每条条文都在章节里(交付层不另起炉灶)
    assert scan["total"] >= 1 and "规范校核" in cs
    for res in scan["results"]:
        assert res.rule_id in cs, f"整体校核条文 {res.rule_id} 未出现在计算书章节(数据分叉)"


def test_ssm_is_single_source_no_remodel():
    """同一 Project 两次投影 SSM 内容一致(确定性、无重新建模漂移)。"""
    p = _model()
    a = ssm_from_project(p, "CN"); b = ssm_from_project(p, "CN")
    assert a["meta"]["n_members"] == b["meta"]["n_members"]
    assert a["members"] == b["members"], "SSM 投影非确定性(数据源不稳定)"


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
