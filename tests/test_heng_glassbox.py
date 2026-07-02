"""玻璃盒协议四条(设计书 §6.1)的可回归守护：可溯源/可编辑/可复核/可关闭。

设计书把这四条定为"全部 AI 能力的宪法"。本测试把它们变成断言：
- 可溯源：每条判定挂 rule_id+条文号+计算中间量
- 可编辑：改一个输入，判定确定性翻转(下游重算)
- 可复核：决策日志含 输入/检索条文/中间量/判定/裁决者
- 可关闭：规范校核路径静态审计零 AI/网络依赖(关掉 AI 仍完整可用)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng import glassbox
from heng.codes.registry import get


def test_traceable_all_rules():
    rep = glassbox.glassbox_audit()
    assert rep["traceable"], f"以下规则判定缺 rule_id/条文/中间量: {rep['traceable_fail']}"


def test_deterministic_same_in_same_out():
    rep = glassbox.glassbox_audit()
    assert rep["deterministic"], f"以下规则非确定性: {rep['deterministic_fail']}"


def test_editable_propagates():
    """改柱配筋率 rho，判定确定性从满足→不满足(下游重算)。一级柱 rho_min=0.009。"""
    r = get("CN.GB50011-2010(2016).6.3.7")
    ctx = {"element": "column", "material": "reinforced_concrete", "grade": "一级"}
    assert glassbox.editable_propagates(r, ctx, "rho", 0.012, 0.005)


def test_auditable_decision_log():
    r = get("CN.GB50011-2010(2016).6.3.7")
    log = glassbox.decision_log(r, {"element": "column", "material": "reinforced_concrete",
                                    "grade": "一级", "rho": 0.005})
    for k in ("rule_id", "inputs", "retrieved_clause", "intermediate", "verdict", "adjudicator"):
        assert k in log, f"决策日志缺字段 {k}"
    assert log["adjudicator"] == "deterministic_rule_engine"   # AI 永不签字
    assert log["verdict"] is False and log["retrieved_clause"]["mandatory"] is True


def test_closeable_ai_free_path():
    """可关闭：合规校核路径不得 import 任何 AI/网络模块。"""
    ok, offenders = glassbox.ai_free_check_path()
    assert ok, f"校核路径存在 AI/网络依赖(破坏可关闭): {offenders}"


def test_render_and_all_pass():
    rep = glassbox.glassbox_audit()
    assert rep["all_pass"], rep
    md = glassbox.render_markdown(rep)
    assert "可溯源" in md and "可编辑" in md and "可复核" in md and "可关闭" in md
    assert "AI 永不签字" in md


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
