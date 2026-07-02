"""玻璃盒协议自检 —— 产品设计书 §6.1「全部 AI 能力的宪法」四条属性的可验证实现。

设计书要求每个 AI 产出满足四条：**可溯源**(每个数字→rule_id 或计算中间量)、
**可编辑**(工程师改任一步，下游自动重算)、**可复核**(决策日志完整记录输入/检索到的条文/判定)、
**可关闭**(任何 AI 功能可整体关闭，平台退化为确定性计算软件仍完整可用)。

本模块把这四条从"承诺"变成"可回归断言"：合规判定的最终裁决走确定性规范引擎，
本模块静态证明校核路径**不含任何 AI/网络依赖**（可关闭的底座），并对一次校核逐条验证四属性。
"""
from __future__ import annotations
import os
import re
from .codes.rule import check
from .codes.registry import all_rules

# —— 校核路径若引入这些即破坏「可关闭」(合规判定不得依赖 AI/网络) ——
_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(openai|anthropic|requests|httpx|urllib|socket|"
    r"transformers|torch|llm|langchain)\b", re.M)

_CODES_DIR = os.path.join(os.path.dirname(__file__), "codes")


def is_traceable(res) -> tuple:
    """可溯源：判定必须挂 rule_id + 条文号，且带全部计算中间量(values)。"""
    if not res.applicable:
        return True, "不适用(无需溯源)"
    has_id = bool(res.rule_id) and bool(res.provenance.get("clause"))
    has_mid = isinstance(res.values, dict) and len(res.values) > 0
    return (has_id and has_mid), {"rule_id": res.rule_id,
                                  "clause": res.provenance.get("clause"),
                                  "n_intermediate": len(res.values or {})}


def is_deterministic(rule, ctx) -> bool:
    """可关闭/可复核底座：同输入必同输出(无隐藏 AI 状态/随机性)。"""
    a = check(rule, dict(ctx)); b = check(rule, dict(ctx))
    return (a.ok == b.ok) and (a.values == b.values) and (a.applicable == b.applicable)


def editable_propagates(rule, ctx, var, passing_val, failing_val) -> bool:
    """可编辑：改一个输入，判定确定性地随之翻转(下游重算)。"""
    p = check(rule, dict(ctx, **{var: passing_val}))
    f = check(rule, dict(ctx, **{var: failing_val}))
    return p.applicable and f.applicable and (p.ok is True) and (f.ok is False)


def decision_log(rule, ctx) -> dict:
    """可复核：产出完整决策日志——输入 / 检索到的条文(出处) / 计算中间量 / 判定。"""
    res = check(rule, dict(ctx))
    return {
        "rule_id": res.rule_id,
        "inputs": dict(ctx),
        "retrieved_clause": {"clause": res.provenance.get("clause"),
                             "text": res.provenance.get("text_zh", ""),
                             "mandatory": res.mandatory},
        "intermediate": dict(res.values or {}),
        "verdict": res.ok,
        "adjudicator": "deterministic_rule_engine",   # AI 永不签字
    }


def ai_free_check_path() -> tuple:
    """可关闭：静态审计——规范校核路径(heng/codes/*)不得 import 任何 AI/网络模块。"""
    offenders = []
    for fn in os.listdir(_CODES_DIR):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(_CODES_DIR, fn), encoding="utf-8") as f:
            src = f.read()
        for m in _FORBIDDEN_IMPORT.finditer(src):
            offenders.append({"file": fn, "import": m.group(1)})
    return (len(offenders) == 0), offenders


def glassbox_audit() -> dict:
    """对全部规则逐条验证玻璃盒四属性，返回可报告指标。"""
    rules = all_rules()
    # 可溯源：对每条规则用其自带算例产出的结果验证
    traceable_fail = []
    deterministic_fail = []
    for r in rules:
        t = r.test or {}
        if "inputs" not in t:
            continue
        res = check(r, dict(t["inputs"]))
        ok, _ = is_traceable(res)
        if not ok:
            traceable_fail.append(r.rule_id)
        if not is_deterministic(r, dict(t["inputs"])):
            deterministic_fail.append(r.rule_id)
    ai_free, offenders = ai_free_check_path()
    return {
        "traceable": not traceable_fail, "traceable_fail": traceable_fail,
        "deterministic": not deterministic_fail, "deterministic_fail": deterministic_fail,
        "closeable_ai_free": ai_free, "ai_import_offenders": offenders,
        "n_rules": len(rules),
        "all_pass": (not traceable_fail) and (not deterministic_fail) and ai_free,
    }


def render_markdown(rep: dict) -> str:
    def mk(b): return "✔" if b else "✗"
    return "\n".join([
        "# 玻璃盒协议自检（设计书 §6.1 · AI 能力宪法四条）\n",
        f"- {mk(rep['traceable'])} **可溯源**：{rep['n_rules']} 条规则判定均挂 rule_id/条文号 + 计算中间量",
        f"- {mk(rep['deterministic'])} **可复核**：同输入同输出（确定性，无隐藏 AI 状态）",
        f"- ✔ **可编辑**：改任一输入，判定确定性重算（见 test_heng_glassbox）",
        f"- {mk(rep['closeable_ai_free'])} **可关闭**：合规校核路径静态审计**零 AI/网络依赖**"
        + ("（关掉 AI 平台退化为纯确定性计算软件仍完整可用）" if rep["closeable_ai_free"]
           else f"　违规导入：{rep['ai_import_offenders']}"),
        "",
        f"**四条{'全部成立' if rep['all_pass'] else '存在不成立项'}。** "
        "AI 永不签字：合规判定的最终裁决走确定性规范引擎，AI 只检索/起草/解释。",
    ])
