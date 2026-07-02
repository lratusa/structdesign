"""中国 GB 规范规则（由 structdesign/codes 硬编码校核**重构**为 Code-as-Data）。

每条 Rule 附**手算基准**测试用例(test)，`test_heng_rules.py` 全跑 = 规范库 CI(设计书 §4.1)。
rule_id = 辖区.规范-版本.条号。强条(mandatory)对应 GB 55 系列全文强制。
"""
from __future__ import annotations
from .rule import Rule

RULES_CN_GB = [
    Rule(
        rule_id="CN.GB50010-2010(2015).8.5.1",
        title="纵向受力钢筋最小配筋率(受弯构件)",
        scope={"element": ["beam", "slab"], "material": "reinforced_concrete"},
        formula={
            "assign": ["rho_min = max(0.002, 0.45*ft/fy)"],
            "verdict": "rho >= rho_min",
        },
        provenance={"text_zh": "钢筋混凝土受弯构件纵向受拉钢筋最小配筋率取 0.20% 与 45ft/fy% 的较大值。",
                    "clause": "8.5.1", "page": 89, "mandatory": True},
        lineage={"supersedes": "CN.GB50010-2002.9.5.1", "superseded_by": None,
                 "effective": "2015-09-01"},
        test={"inputs": {"element": "beam", "material": "reinforced_concrete",
                          "ft": 1.43, "fy": 360, "rho": 0.003},
              "expect": {"rho_min": 0.002, "verdict": True}},   # 0.45*1.43/360=0.00179<0.002
    ),
    Rule(
        rule_id="CN.GB50011-2010(2016).6.3.6",
        title="框架柱轴压比限值",
        scope={"element": ["column"], "material": "reinforced_concrete"},
        formula={
            "assign": ["mu_lim = 0.65 if grade=='一级' else 0.75 if grade=='二级' "
                       "else 0.85 if grade=='三级' else 0.90"],
            "verdict": "mu <= mu_lim",
        },
        provenance={"text_zh": "抗震设计时框架柱的轴压比不宜超过表 6.3.6 的限值(一级0.65/二级0.75/三级0.85/四级0.90)。",
                    "clause": "6.3.6", "page": 58, "mandatory": False},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "column", "material": "reinforced_concrete",
                          "grade": "二级", "mu": 0.70},
              "expect": {"mu_lim": 0.75, "verdict": True}},
    ),
    Rule(
        rule_id="CN.GB50011-2010(2016).5.5.1",
        title="多遇地震下弹性层间位移角限值",
        scope={"element": ["story"]},
        formula={
            "assign": ["theta_lim = 1/550 if system=='frame' else 1/800"],
            "verdict": "drift <= theta_lim",
        },
        provenance={"text_zh": "多遇地震作用下楼层最大弹性层间位移角限值：框架 1/550，框架-剪力墙/框架-核心筒 1/800。",
                    "clause": "5.5.1", "page": 47, "mandatory": True},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "story", "system": "frame", "drift": 0.001667},
              "expect": {"verdict": True}},   # 1/600 ≤ 1/550
    ),
    Rule(
        rule_id="CN.GB50011-2010(2016).3.4.5",
        title="扭转为主的第一周期与平动为主的第一周期之比(周期比)",
        scope={"element": ["structure"]},
        formula={"verdict": "period_ratio <= 0.90"},
        provenance={"text_zh": "结构扭转为主的第一自振周期 Tt 与平动为主的第一自振周期 T1 之比，"
                               "A 级高度高层不应大于 0.9。",
                    "clause": "3.4.5", "page": 22, "mandatory": False},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "structure", "period_ratio": 0.85}, "expect": {"verdict": True}},
    ),
    Rule(
        rule_id="CN.GB50011-2010(2016).3.4.3",
        title="楼层最大水平位移与平均位移之比(位移比)",
        scope={"element": ["structure"]},
        formula={"assign": ["disp_lim = 1.2"], "verdict": "disp_ratio <= disp_lim"},
        provenance={"text_zh": "在偶然偏心地震作用下，楼层最大弹性水平位移与平均值之比不宜大于 1.2，"
                               "不应大于 1.5。",
                    "clause": "3.4.3", "page": 21, "mandatory": False},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "structure", "disp_ratio": 1.1},
              "expect": {"disp_lim": 1.2, "verdict": True}},
    ),
    Rule(
        rule_id="CN.GB50011-2010(2016).5.2.5",
        title="楼层最小地震剪力系数(剪重比)",
        scope={"element": ["structure"]},
        formula={
            "assign": ["lam_min = lookup(intensity, ['6','7','7.5','8','8.5','9'], "
                       "[0.008,0.016,0.024,0.032,0.048,0.064])"],
            "verdict": "shear_weight >= lam_min",
        },
        provenance={"text_zh": "抗震验算时，结构任一楼层的水平地震剪力应满足最小地震剪力系数(表5.2.5)要求。",
                    "clause": "5.2.5", "page": 44, "mandatory": True},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "structure", "intensity": "8", "shear_weight": 0.035},
              "expect": {"lam_min": 0.032, "verdict": True}},
    ),

    # ---------------- 构件级配筋校核（柱/墙/梁） ----------------
    Rule(
        rule_id="CN.GB50011-2010(2016).6.3.7",
        title="框架柱全部纵向钢筋最小配筋率",
        scope={"element": ["column"], "material": "reinforced_concrete"},
        formula={
            "assign": ["rho_min = 0.009 if grade=='一级' else 0.007 if grade=='二级' "
                       "else 0.006 if grade=='三级' else 0.005"],
            "verdict": "rho >= rho_min",
        },
        provenance={"text_zh": "抗震设计时框架柱全部纵向受力钢筋的最小配筋百分率(表6.3.7-1，中/边柱)。",
                    "clause": "6.3.7", "page": 59, "mandatory": True},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "column", "material": "reinforced_concrete",
                          "grade": "二级", "rho": 0.012},
              "expect": {"rho_min": 0.007, "verdict": True}},
    ),
    Rule(
        rule_id="CN.GB50010-2010(2015).9.3.1",
        title="柱全部纵向钢筋最大配筋率",
        scope={"element": ["column"], "material": "reinforced_concrete"},
        formula={"verdict": "rho <= 0.05"},
        provenance={"text_zh": "柱中全部纵向钢筋的配筋率不宜大于 5%。",
                    "clause": "9.3.1", "page": 105, "mandatory": False},
        lineage={"effective": "2015-09-01"},
        test={"inputs": {"element": "column", "material": "reinforced_concrete", "rho": 0.03},
              "expect": {"verdict": True}},
    ),
    Rule(
        rule_id="CN.GB50010-2010(2015).6.3.1",
        title="受弯构件斜截面受剪截面限制条件(剪压比)",
        scope={"element": ["beam"], "material": "reinforced_concrete"},
        formula={
            # hw/b ≤ 4：V ≤ 0.25·βc·fc·b·h0（βc≤C50 取1.0），单位 kN
            "assign": ["Vlim = 0.25*betac*fc*b*h0/1000"],
            "verdict": "V <= Vlim",
        },
        provenance={"text_zh": "矩形截面受弯构件，当 hw/b≤4 时，其受剪截面应满足 V≤0.25βcfcbh0。",
                    "clause": "6.3.1", "page": 61, "mandatory": True},
        lineage={"effective": "2015-09-01"},
        test={"inputs": {"element": "beam", "material": "reinforced_concrete",
                          "betac": 1.0, "fc": 14.3, "b": 300, "h0": 660, "V": 200},
              "expect": {"Vlim": 707.85, "verdict": True}},   # 0.25*1*14.3*300*660/1000
    ),
    Rule(
        rule_id="CN.GB50011-2010(2016).6.4.2",
        title="剪力墙墙肢轴压比限值",
        scope={"element": ["wall"], "material": "reinforced_concrete"},
        formula={
            "assign": ["mu_lim = 0.4 if (grade=='一级' and intensity=='9') else "
                       "(0.5 if (grade=='一级' or grade=='二级') else 0.6)"],
            "verdict": "mu <= mu_lim",
        },
        provenance={"text_zh": "一、二、三级剪力墙墙肢的轴压比不宜超过表6.4.2的限值(一级9度0.4/一二级0.5/三级0.6)。",
                    "clause": "6.4.2", "page": 62, "mandatory": False},
        lineage={"effective": "2016-08-01"},
        test={"inputs": {"element": "wall", "material": "reinforced_concrete",
                          "grade": "二级", "intensity": "8", "mu": 0.5},
              "expect": {"mu_lim": 0.5, "verdict": True}},
    ),
]
