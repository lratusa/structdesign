"""控制条文标注（设计书 §6.2 「每个优化结果附控制条文标注——哪条规范卡住了它」）。

对一个构件上下文，跑全部适用规则，计算每条的**紧迫度**(criticality：demand/capacity，
=1 即恰在规范边界，>1 违规，<1 富余)，返回**控制条文**(紧迫度最高者)——即"卡住这个构件"的那条规范。

紧迫度通过受限 DSL 直接对每条规则的 verdict 两侧求值得到，故对任意 rule_id 通用、无需硬编码。
玻璃盒：控制条文带 rule_id/条文号/两侧数值，可溯源。
"""
from __future__ import annotations
import re
from .codes.registry import rules_for
from .codes.rule import check
from .codes.dsl import evaluate, DSLError

_CMP = re.compile(r"\s*(>=|<=|>|<)\s*")


def _criticality(verdict: str, env: dict):
    """返回 (criticality, lhs_val, rhs_val, op)；无法解析或非单一比较则 None。"""
    parts = _CMP.split(verdict.strip())
    if len(parts) != 3:                 # 仅处理单一比较(如 'rho >= rho_min')
        return None
    lhs, op, rhs = parts
    try:
        a = evaluate(lhs, env)
        b = evaluate(rhs, env)
    except DSLError:
        return None
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if op in (">=", ">"):               # 下限约束 demand≥limit：紧迫度=limit/demand
        crit = (b / a) if a not in (0,) else float("inf")
    else:                               # 上限约束 demand≤limit：紧迫度=demand/limit
        crit = (a / b) if b not in (0,) else float("inf")
    return crit, a, b, op


def governing_clause(ctx: dict, jurisdiction: str = "CN") -> dict:
    """返回控制条文 + 全部适用条文的紧迫度排名。"""
    ranked = []
    for r in rules_for(jurisdiction):
        res = check(r, ctx)
        if not res.applicable or res.ok is None:
            continue
        v = r.formula.get("verdict", "")
        crit = _criticality(v, dict(ctx, **(res.values or {})))
        if crit is None:
            continue
        c, a, b, op = crit
        ranked.append({"rule_id": r.rule_id, "clause": r.provenance.get("clause"),
                       "title": r.title, "criticality": round(c, 4),
                       "demand": a, "capacity": b, "op": op,
                       "ok": res.ok, "mandatory": res.mandatory})
    ranked.sort(key=lambda x: x["criticality"], reverse=True)
    return {"governing": ranked[0] if ranked else None, "ranked": ranked,
            "n_applicable": len(ranked)}


def annotate(ctx: dict, jurisdiction: str = "CN") -> str:
    """一句话控制条文标注，供优化结果/配筋表旁注。"""
    g = governing_clause(ctx, jurisdiction)["governing"]
    if not g:
        return "无适用可量化条文"
    util = g["criticality"]
    state = "已达/超限" if util >= 1.0 - 1e-9 else f"利用率 {util*100:.0f}%"
    return f"控制条文：{g['title']}（{g['clause']}，{state}）"
