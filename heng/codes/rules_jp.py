"""日本规范规则 seed（建築基準法施行令）——设计书 §4.2 日本包 / 多国覆盖。

首批取施行令中判定明确的强制条文。全量告示体系(平12建告1459号等)+限界耐力計算为 Phase 2，
须由日本籍構造設計一級建築士团队审定。rule_id 用 JP.规范.条号。
"""
from __future__ import annotations
from .rule import Rule

RULES_JP = [
    Rule(
        rule_id="JP.建築基準法施行令.77",
        title="柱の主筋の最小量（コンクリート断面積の0.8%以上）",
        concept="column_min_longitudinal",
        scope={"element": ["column"], "material": "reinforced_concrete"},
        formula={"verdict": "rho >= 0.008"},
        provenance={"text_zh": "施行令第77条：柱の主筋の断面積の和は、コンクリートの断面積の0.8%以上とする。",
                    "clause": "第77条", "mandatory": True},
        lineage={"effective": "1950-11-23"},
        test={"inputs": {"element": "column", "material": "reinforced_concrete", "rho": 0.010},
              "expect": {"verdict": True}},
    ),
    Rule(
        rule_id="JP.建築基準法施行令.82の2",
        title="層間変形角の制限（1/200以内）",
        concept="story_drift",
        scope={"element": ["story"]},
        formula={"assign": ["drift_lim = 0.005"], "verdict": "drift <= drift_lim"},
        provenance={"text_zh": "施行令第82条の2：地震力による各階の層間変形角は、原則として1/200以内とする。",
                    "clause": "第82条の2", "mandatory": True},
        lineage={"effective": "1981-06-01"},
        test={"inputs": {"element": "story", "drift": 0.003}, "expect": {"verdict": True}},
    ),
]
