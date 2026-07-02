"""中国水工规范规则（SL/NB）——设计书 §7 水工差异化主场。

把规范引擎从"建筑"扩展到"水工"域：新增构件类型(重力坝/水闸)。刚体极限平衡稳定校核入引擎，
每条附手算基准。演示平台的多域(建筑+水工)统一数据模型。
"""
from __future__ import annotations
from .rule import Rule

RULES_CN_SL_NB = [
    Rule(
        rule_id="CN.NBT35026-2014.坝基抗滑稳定",
        title="重力坝坝基面抗滑稳定安全系数(抗剪断公式)",
        concept="sliding_stability",
        scope={"element": ["gravity_dam"]},
        formula={
            # K' = (f'·ΣW + c'·A) / ΣP，f'抗剪断摩擦系数, c'凝聚力(kPa), A 接触面积(m²)
            "assign": ["Ks = (f_prime*sumW + c_prime*A) / sumP"],
            "verdict": "Ks >= K_allow",
        },
        provenance={"text_zh": "重力坝沿坝基面抗滑稳定按抗剪断公式 K'=(f'ΣW+c'A)/ΣP 计算，"
                               "基本组合安全系数 [K']=3.0。",
                    "clause": "抗剪断公式", "mandatory": True},
        lineage={"effective": "2014-11-01"},
        test={"inputs": {"element": "gravity_dam", "f_prime": 1.0, "c_prime": 900.0,
                          "A": 50.0, "sumW": 50000.0, "sumP": 18000.0, "K_allow": 3.0},
              "expect": {"verdict": True}},   # Ks=(50000+45000)/18000=5.28≥3.0
    ),
    Rule(
        rule_id="CN.SL265-2016.水闸抗浮",
        title="水闸抗浮稳定安全系数",
        concept="antifloat_stability",
        scope={"element": ["sluice", "gate"]},
        formula={"assign": ["Kf = sumG / sumU"], "verdict": "Kf >= Kf_allow"},
        provenance={"text_zh": "水闸抗浮稳定安全系数 Kf=ΣG/ΣU 不应小于允许值(基本组合 1.10)。",
                    "clause": "抗浮稳定", "mandatory": True},
        lineage={"effective": "2016-05-01"},
        test={"inputs": {"element": "sluice", "sumG": 12000.0, "sumU": 9000.0, "Kf_allow": 1.10},
              "expect": {"Kf": 1.3333, "verdict": True}},
    ),
    Rule(
        rule_id="CN.SL265-2016.水闸抗滑",
        title="水闸沿底板抗滑稳定安全系数",
        concept="sliding_stability",
        scope={"element": ["sluice", "gate"]},
        formula={"assign": ["Kc = f*sumW / sumP"], "verdict": "Kc >= Kc_allow"},
        provenance={"text_zh": "水闸沿地基面抗滑稳定安全系数 Kc=f·ΣW/ΣP 不应小于允许值。",
                    "clause": "抗滑稳定", "mandatory": True},
        lineage={"effective": "2016-05-01"},
        test={"inputs": {"element": "sluice", "f": 0.5, "sumW": 20000.0, "sumP": 3000.0, "Kc_allow": 1.25},
              "expect": {"Kc": 3.3333, "verdict": True}},
    ),
]
