"""规范知识图谱依据链(设计书 §4.3)：条文引用关系展开 + 图完整性。

验证：
- 剪重比 5.2.5 的依据链能展开到地震作用中间节点，再到 GB50009 荷载组合叶节点(传递闭包)。
- 依据链无悬空引用(形似 rule_id 的引用要么在注册表、要么是已定义中间节点)。
- 防环：自引用/环路不会无限递归。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.refgraph import dependency_chain, flatten, validate, render_markdown, REFERENCES, is_executable


def test_transitive_chain_expands():
    chain = dependency_chain("CN.GB50011-2010(2016).5.2.5")
    nodes = flatten(chain)
    # 剪重比 → 地震作用(中间) → GB50009 荷载组合(叶)
    assert "CN.GB50011-2010(2016).地震作用" in nodes
    assert any("GB 50009" in n for n in nodes), nodes


def test_no_dangling_refs():
    rep = validate()
    assert rep["ok"], f"存在悬空引用: {rep['dangling']}"
    assert rep["external_leaves"] >= 1 and rep["internal_refs"] >= 0


def test_executable_flag():
    # 剪重比本身是注册表规则
    assert is_executable("CN.GB50011-2010(2016).5.2.5")
    # 外部规范是叶(不可执行)
    assert not is_executable("GB 50009-2012 §3(荷载组合)")


def test_cycle_safe():
    """人为制造环不应无限递归。"""
    bak = dict(REFERENCES)
    try:
        REFERENCES["X.self"] = [{"ref": "X.self", "relation": "依据"}]
        chain = dependency_chain("X.self")
        # 能返回且标记环
        assert chain["children"][0].get("cycle") is True
    finally:
        REFERENCES.clear(); REFERENCES.update(bak)


def test_render():
    md = render_markdown("CN.GB50011-2010(2016).5.2.5")
    assert "依据链" in md and "地震作用" in md and "GB 50009" in md


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
