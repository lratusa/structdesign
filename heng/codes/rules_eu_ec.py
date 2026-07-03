"""Eurocode 规则（演示 NDP 参数覆盖层 + 多国并行，设计书 §4.2/§4.4）。

同一条 EC 规则，切换国别只替换 NDP(National Determined Parameters)参数集，不复制规则本体。
NDP 由 `ndp` 上下文传入(见 ndp.py)；规则体引用 ndp_* 变量。
"""
from __future__ import annotations
from .rule import Rule

RULES_EU_EC = [
    Rule(
        rule_id="EU.EN1992-1-1.9.2.1.1",
        title="梁最小受拉配筋率(min reinforcement)",
        concept="min_flexural_reinforcement",
        scope={"element": ["beam"], "material": "reinforced_concrete"},
        formula={
            # As,min/(bt·d) = max(k_c1·fctm/fyk, k_c2)；k_c1/k_c2 为 NDP(推荐 0.26/0.0013)
            "assign": ["rho_min = max(ndp_kc1*fctm/fyk, ndp_kc2)"],
            "verdict": "rho >= rho_min",
        },
        provenance={"text_zh": "As,min = max(0.26·fctm/fyk, 0.0013)·bt·d (系数为 NDP，可按各国 National Annex 调整)。",
                    "clause": "9.2.1.1(1)", "mandatory": True},
        lineage={"effective": "2004-12-01"},
        test={"inputs": {"element": "beam", "material": "reinforced_concrete",
                          "fctm": 2.9, "fyk": 500, "rho": 0.003,
                          "ndp_kc1": 0.26, "ndp_kc2": 0.0013},
              "expect": {"rho_min": 0.0015080, "verdict": True}},  # 0.26*2.9/500=0.0015080>0.0013
    ),
    Rule(
        rule_id="EU.EN1998-1.4.4.3.2",
        title="损伤极限状态层间位移限制(damage limitation)",
        concept="story_drift",
        scope={"element": ["story"]},
        formula={
            # dr·ν ≤ 0.005·h（脆性非结构构件）；此处以折减后位移角限值 0.005 表达(ν 见说明)
            "assign": ["drift_lim = 0.005"],
            "verdict": "drift <= drift_lim",
        },
        provenance={"text_zh": "EN 1998-1 §4.4.3.2：损伤极限状态下，含脆性非结构构件的建筑 "
                               "dr·ν ≤ 0.005·h（ν 为重要性折减系数；延性非结构 0.0075、无约束 0.010）。",
                    "clause": "4.4.3.2", "mandatory": False},
        lineage={"effective": "2004-12-01"},
        test={"inputs": {"element": "story", "drift": 0.004},
              "expect": {"drift_lim": 0.005, "verdict": True}},
    ),
    Rule(
        rule_id="EU.EN1998-1.5.4.3.2.2",
        title="柱纵向配筋率下限(DCM，1%)",
        concept="column_min_longitudinal",
        scope={"element": ["column"], "material": "reinforced_concrete"},
        formula={"assign": ["rho_min = 0.01"], "verdict": "rho >= rho_min"},
        provenance={"text_zh": "EN 1998-1 §5.4.3.2.2：中等延性(DCM)抗震柱纵向配筋率 ρl 取 0.01～0.04。",
                    "clause": "5.4.3.2.2", "mandatory": False},
        lineage={"effective": "2004-12-01"},
        test={"inputs": {"element": "column", "material": "reinforced_concrete", "rho": 0.02},
              "expect": {"rho_min": 0.01, "verdict": True}},
    ),
    Rule(
        rule_id="EU.EN1992-1-1.9.2.1.1max",
        title="梁最大受拉配筋率(max reinforcement)",
        concept="max_flexural_reinforcement",
        scope={"element": ["beam"], "material": "reinforced_concrete"},
        formula={
            # As,max = 0.04·Ac (NDP，推荐 0.04)
            "assign": ["rho_max = ndp_asmax"],
            "verdict": "rho <= rho_max",
        },
        provenance={"text_zh": "EN 1992-1-1 §9.2.1.1(3)：梁受拉与受压区最大配筋 As,max = 0.04·Ac "
                               "(系数为 NDP，推荐 0.04)。",
                    "clause": "9.2.1.1(3)", "mandatory": False},
        lineage={"effective": "2004-12-01"},
        test={"inputs": {"element": "beam", "material": "reinforced_concrete",
                          "rho": 0.02, "ndp_asmax": 0.04},
              "expect": {"rho_max": 0.04, "verdict": True}},
    ),
]
