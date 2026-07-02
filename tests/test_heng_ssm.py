"""SSM Git 式版本化：commit/branch/tag/diff(修改对照表) + 审计 + Project 投影。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.ssm import SSMRepo, ssm_from_project, _diff_ssm
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project


def _ssm():
    return {"members": {"KZ0": {"type": "column", "b": 500, "h": 500}},
            "materials": {}, "loads": {"live": {"kind": "live", "value": 2.0}}}


def test_commit_chain_and_checkout():
    repo = SSMRepo()
    s = _ssm()
    c1 = repo.commit(s, "初始模型", "工程师A")
    s["members"]["KZ0"]["b"] = 600
    c2 = repo.commit(s, "柱加大到600", "工程师A")
    assert c1 != c2
    assert repo.checkout(c1)["members"]["KZ0"]["b"] == 500     # 历史版本可回溯
    assert repo.checkout("main")["members"]["KZ0"]["b"] == 600
    assert len(repo.log()) == 2


def test_content_addressing_deterministic():
    r1, r2 = SSMRepo(), SSMRepo()
    a = r1.commit(_ssm(), "m", "u"); b = r2.commit(_ssm(), "m", "u")
    assert a == b                                             # 同内容→同 commit id


def test_branch_and_tag_signed():
    repo = SSMRepo(); repo.commit(_ssm(), "init", "A")
    repo.branch("方案B")
    s = _ssm(); s["members"]["KZ0"]["h"] = 700
    repo.commit(s, "方案B改H", "A", branch="方案B")
    cid = repo.tag("送审v1", "main", signature="张三-注册章")
    assert repo.tags["送审v1"] == cid
    assert repo.commits[cid].signature == "张三-注册章"       # 签名tag
    assert repo.checkout("方案B")["members"]["KZ0"]["h"] == 700
    assert repo.checkout("main")["members"]["KZ0"]["h"] == 500


def test_diff_change_table():
    """修改对照表：加大截面 + 删构件 + 改荷载 → diff 逐项列出。"""
    repo = SSMRepo()
    s = {"members": {"KZ0": {"b": 500, "h": 500}, "KZ1": {"b": 500, "h": 500}},
         "materials": {}, "loads": {"live": {"value": 2.0}}}
    repo.tag("送审v1", repo.commit(s, "v1", "A"))
    s2 = {"members": {"KZ0": {"b": 600, "h": 500}},          # KZ0 改b, KZ1 删除
          "materials": {}, "loads": {"live": {"value": 3.0}}}  # 活载改
    repo.tag("送审v2", repo.commit(s2, "v2", "A"))
    d = repo.diff("送审v1", "送审v2")
    assert d["members"]["removed"] == ["KZ1"]
    mod = d["members"]["modified"]
    assert len(mod) == 1 and mod[0]["id"] == "KZ0"
    assert mod[0]["fields"]["b"] == [500, 600]
    assert d["loads"]["modified"][0]["fields"]["value"] == [2.0, 3.0]


def test_audit_log_complete():
    repo = SSMRepo()
    repo.commit(_ssm(), "init", "A"); repo.branch("b1"); repo.tag("t1")
    actions = [a[0] for a in repo.audit]
    assert actions == ["commit", "branch", "tag"]            # 全量审计


def test_project_projection():
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B]
    cols = [Column(x, y, 500, 500) for x in xs for y in ys]
    beams = [Beam(xs[i], 0, xs[i + 1], 0, 300, 600) for i in range(2)]
    fl = StandardFloor(columns=cols, beams=beams, walls=[], slab=SlabLoad(6, 2.5))
    p = Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 5)], seismic=Seismic())
    ssm = ssm_from_project(p, "CN")
    assert ssm["design_context"]["jurisdiction"] == "CN"
    assert ssm["loads"]["slab_dead"]["value"] == 6
    assert len([m for m in ssm["members"].values() if m["type"] == "column"]) == 6
    # 可直接进版本库
    repo = SSMRepo(); c = repo.commit(ssm, "从Project建模", "A")
    assert repo.checkout(c)["design_context"]["seismic"]["grade"] == "二级"


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
