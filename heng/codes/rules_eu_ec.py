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
]
