"""规则注册表 + 全量校核（设计书 §8 ④：规范引擎全量条文扫描）。"""
from __future__ import annotations
from typing import List
from .rule import Rule, CheckResult, check
from .rules_cn_gb import RULES_CN_GB
from .rules_eu_ec import RULES_EU_EC

_ALL: List[Rule] = list(RULES_CN_GB) + list(RULES_EU_EC)
REGISTRY = {r.rule_id: r for r in _ALL}


def all_rules() -> List[Rule]:
    return list(REGISTRY.values())


def get(rule_id: str) -> Rule:
    return REGISTRY[rule_id]


def rules_for(jurisdiction: str, current_only: bool = True) -> List[Rule]:
    """某辖区的规则集。current_only：只取现行(未被替代)条文。"""
    out = []
    for r in REGISTRY.values():
        if r.jurisdiction != jurisdiction:
            continue
        if current_only and r.lineage.get("superseded_by"):
            continue
        out.append(r)
    return out


def check_all(ctx: dict, jurisdiction: str, current_only: bool = True) -> List[CheckResult]:
    """对上下文跑该辖区全部适用规则，返回结果列表(含不适用的标记)。"""
    return [check(r, ctx) for r in rules_for(jurisdiction, current_only)]


def scan(ctx: dict, jurisdiction: str) -> dict:
    """校核摘要：适用条文的通过/不通过 + 强条红线(设计书 §8 强条零容忍)。"""
    res = [r for r in check_all(ctx, jurisdiction) if r.applicable and r.ok is not None]
    fail = [r for r in res if not r.ok]
    mand_fail = [r for r in fail if r.mandatory]
    return dict(total=len(res), passed=sum(1 for r in res if r.ok), failed=len(fail),
                mandatory_failed=len(mand_fail), results=res,
                red_line=bool(mand_fail))          # 强条不满足 = 红线
