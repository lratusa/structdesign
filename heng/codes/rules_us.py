"""美国规范规则 seed（ACI 318-19 / ASCE 7-22）——设计书 §4.2 北美包 / 多国覆盖。

把 US 从"辖区可解析"升级为"有条文库"。首批取判定明确的条文。全量(ACI 318 全章 + ASCE 7 荷载/
地震 + AISC 360 钢结构)属 Phase 3，须由持 PE/SE 执照的美方工程师审定。rule_id 用 US.规范-版本.条号。

单位：ACI/ASCE 用美制(psi)。跨国对照中**层间位移角(story_drift)为无量纲比值**，故 CN/JP/US 可直接同 ctx 对照；
配筋率类含材料强度单位(psi vs MPa)，对照需上下文单位自洽（映射只解释差异不换算，见 dualcode）。
"""
from __future__ import annotations
from .rule import Rule

RULES_US = [
    Rule(
        rule_id="US.ACI318-19.9.6.1.2",
        title="梁受弯最小配筋(minimum flexural reinforcement)",
        concept="min_flexural_reinforcement",
        scope={"element": ["beam"], "material": "reinforced_concrete"},
        formula={
            # As,min = max(3√f'c/fy, 200/fy)·bw·d（f'c、fy 单位 psi）→ 配筋率形式
            "assign": ["rho_min = max(3*sqrt(fc)/fy, 200/fy)"],
            "verdict": "rho >= rho_min",
        },
        provenance={"text_zh": "ACI 318-19 §9.6.1.2：受弯构件最小受拉配筋 As,min 取 "
                               "max(3√f'c/fy, 200/fy)·bw·d（f'c、fy 以 psi 计）。",
                    "clause": "9.6.1.2", "mandatory": False},
        lineage={"effective": "2019-01-01"},
        test={"inputs": {"element": "beam", "material": "reinforced_concrete",
                          "fc": 4000, "fy": 60000, "rho": 0.005},
              "expect": {"rho_min": 0.0033333, "verdict": True}},   # max(3√4000/60000, 200/60000)
    ),
    Rule(
        rule_id="US.ACI318-19.10.6.1.1",
        title="柱纵向配筋率下限(1%)",
        concept="column_min_longitudinal",
        scope={"element": ["column"], "material": "reinforced_concrete"},
        formula={"assign": ["rho_min = 0.01"], "verdict": "rho >= rho_min"},
        provenance={"text_zh": "ACI 318-19 §10.6.1.1：柱纵向钢筋配筋率 Ast/Ag 不小于 0.01（且不大于 0.08）。",
                    "clause": "10.6.1.1", "mandatory": False},
        lineage={"effective": "2019-01-01"},
        test={"inputs": {"element": "column", "material": "reinforced_concrete", "rho": 0.02},
              "expect": {"rho_min": 0.01, "verdict": True}},
    ),
    Rule(
        rule_id="US.ASCE7-22.12.12.1",
        title="容许层间位移角(allowable story drift)",
        concept="story_drift",
        scope={"element": ["story"]},
        formula={
            # Table 12.12-1：一般结构(Risk Category I/II) Δa = 0.020·hsx → 位移角限值 0.020
            "assign": ["drift_lim = 0.020"],
            "verdict": "drift <= drift_lim",
        },
        provenance={"text_zh": "ASCE 7-22 §12.12.1 / Table 12.12-1：一般结构(Risk Category I 或 II)的"
                               "容许层间位移 Δa = 0.020·hsx（层高的 2%）。",
                    "clause": "12.12.1", "mandatory": False},
        lineage={"effective": "2022-01-01"},
        test={"inputs": {"element": "story", "drift": 0.01},
              "expect": {"drift_lim": 0.020, "verdict": True}},
    ),
]
