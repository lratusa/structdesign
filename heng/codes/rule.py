"""规则记录(Rule) + 校核结果(CheckResult) —— 设计书 §4.1 / §6.1。

每条可执行规范条文 = 一条 Rule：rule_id / scope / formula(DSL) / provenance / lineage / test。
校核结果带**完整溯源**(rule_id + 原文 + 是否强条 + 全部中间量)，满足玻璃盒"可溯源"。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .dsl import evaluate, evaluate_block, DSLError


@dataclass
class Rule:
    rule_id: str                       # 辖区.规范-版本.条号，如 CN.GB50010-2010(2015).8.5.1
    title: str                         # 简述
    scope: dict = field(default_factory=dict)       # {element:[...], material:..., condition:"DSL"}
    formula: dict = field(default_factory=dict)      # {assign:[...], verdict:"DSL", report:[...]}
    provenance: dict = field(default_factory=dict)   # {text_zh, clause, page, mandatory:bool}
    lineage: dict = field(default_factory=dict)      # {supersedes, superseded_by, effective}
    test: dict = field(default_factory=dict)         # {inputs:{...}, expect:{var:val,..., verdict:bool}}
    concept: str = ""                                # 概念标签(跨国映射用，如 min_flexural_reinforcement)

    @property
    def jurisdiction(self) -> str:
        return self.rule_id.split(".", 1)[0]

    @property
    def mandatory(self) -> bool:        # 强制性条文
        return bool(self.provenance.get("mandatory", False))


@dataclass
class CheckResult:
    rule_id: str
    applicable: bool
    ok: Optional[bool]                 # None=不适用/无判定
    values: dict = field(default_factory=dict)   # 全部中间量(玻璃盒可溯源)
    mandatory: bool = False
    title: str = ""
    provenance: dict = field(default_factory=dict)
    error: str = ""

    def __bool__(self):
        return bool(self.ok)


def _applicable(rule: Rule, ctx: dict) -> bool:
    """scope 是否命中：element/material 集合匹配 + condition(DSL) 为真。"""
    sc = rule.scope or {}
    el = ctx.get("element")
    if "element" in sc and el is not None and el not in sc["element"]:
        return False
    mat = ctx.get("material")
    if "material" in sc and mat is not None and mat != sc["material"]:
        return False
    cond = sc.get("condition")
    if cond:
        try:
            if not evaluate(cond, ctx):
                return False
        except DSLError:
            return False
    return True


def check(rule: Rule, ctx: dict) -> CheckResult:
    """对给定上下文执行一条规则。返回带溯源的结果。"""
    if not _applicable(rule, ctx):
        return CheckResult(rule.rule_id, applicable=False, ok=None,
                           mandatory=rule.mandatory, title=rule.title, provenance=rule.provenance)
    try:
        env = evaluate_block(rule.formula.get("assign", []), ctx)
        verdict = None
        if rule.formula.get("verdict"):
            verdict = bool(evaluate(rule.formula["verdict"], env))
        # 只保留可展示的量（数值/布尔/字符串）
        vals = {k: v for k, v in env.items()
                if isinstance(v, (int, float, bool, str)) and not k.startswith("_")}
        return CheckResult(rule.rule_id, applicable=True, ok=verdict, values=vals,
                           mandatory=rule.mandatory, title=rule.title, provenance=rule.provenance)
    except DSLError as e:
        return CheckResult(rule.rule_id, applicable=True, ok=None,
                           mandatory=rule.mandatory, title=rule.title,
                           provenance=rule.provenance, error=str(e))


def run_selftest(rule: Rule):
    """规范库 CI：用规则自带的官方算例/手算基准校验（设计书 §4.1）。
    返回 (通过?, 说明)。inputs → check → 比对 expect(含各中间量与 verdict)。"""
    t = rule.test or {}
    if "inputs" not in t:
        return None, "无测试用例"
    r = check(rule, dict(t["inputs"]))
    if r.error:
        return False, f"求值错误: {r.error}"
    for k, exp in (t.get("expect") or {}).items():
        if k == "verdict":
            if bool(r.ok) != bool(exp):
                return False, f"verdict 期望 {exp} 实得 {r.ok}"
        else:
            got = r.values.get(k)
            if got is None:
                return False, f"缺中间量 {k}"
            if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
                if abs(got - exp) > 1e-6 + 1e-3 * abs(exp):
                    return False, f"{k} 期望 {exp} 实得 {got}"
            elif got != exp:
                return False, f"{k} 期望 {exp!r} 实得 {got!r}"
    return True, "ok"
