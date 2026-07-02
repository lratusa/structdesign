"""辖区解析器（设计书 §4.3 第一级，**确定性**，不用 AI）。

输入：所在国/地区 + 结构类型 + 委托性质 → 产出生效规范集(规范清单/版本/强条/审查流程)。
这一步必须 100% 正确，故用规则表而非 AI。
NDP(National Annex 参数)按国别提供，供 EC 规则覆盖。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class CodeSet:
    jurisdiction: str
    codes: List[str]              # 生效规范(含版本)
    mandatory: List[str]          # 强制性规范/条文集
    review_process: str           # 审查流程
    ndp: dict = field(default_factory=dict)   # EC National Annex 参数(仅 EU)
    note: str = ""


# 各国 Eurocode National Annex 参数(NDP)——演示：EN1992 最小配筋系数
NDP = {
    "EU-recommended": {"ndp_kc1": 0.26, "ndp_kc2": 0.0013},
    "DE": {"ndp_kc1": 0.26, "ndp_kc2": 0.0013},        # 德国 NA(示例，与推荐值同)
    "GB-UK": {"ndp_kc1": 0.26, "ndp_kc2": 0.0013},
}

# 辖区规范表(建筑结构；水工/日本/北美后续扩展)
_TABLE = {
    "CN": CodeSet(
        jurisdiction="CN",
        codes=["GB 55001-2021(工程结构通用规范)", "GB 55002-2021(建筑与市政抗震通用规范)",
               "GB 50010-2010(2015)", "GB 50011-2010(2016)", "GB 50009-2012", "GB 50017-2017"],
        mandatory=["GB 55001-2021", "GB 55002-2021",
                   "CN.GB50010-2010(2015).8.5.1", "CN.GB50011-2010(2016).5.5.1",
                   "CN.GB50011-2010(2016).5.2.5"],
        review_process="施工图审查(强条零容忍) + 超限高层抗震专项审查(如适用)",
        note="通用规范 GB 55 系列全文强制。"),
    "EU": CodeSet(
        jurisdiction="EU",
        codes=["EN 1990", "EN 1991", "EN 1992-1-1", "EN 1993", "EN 1997", "EN 1998"],
        mandatory=["EU.EN1992-1-1.9.2.1.1"],
        review_process="第三方独立复核(Category 依 EN 1990 Annex B)",
        ndp=NDP["EU-recommended"],
        note="各国 National Annex 通过 NDP 参数覆盖；本例用推荐值。"),
    "JP": CodeSet(
        jurisdiction="JP",
        codes=["建築基準法+施行令", "平12建告1459号 等", "RC規準/S規準(日本建築学会)"],
        mandatory=[],
        review_process="確認申請 + 適合性判定(非認定路线) / 大臣認定(認定版)",
        note="规范条文库待补(Phase 2 日本包)。"),
    "US": CodeSet(
        jurisdiction="US",
        codes=["ASCE 7", "ACI 318", "AISC 360"],
        mandatory=[],
        review_process="AHJ plan review",
        note="规范条文库待补(Phase 3 北美包)。"),
}


_HYDRAULIC = {"gravity_dam", "sluice", "gate", "hydraulic", "水工", "dam", "水闸"}

# 中国水工规范集(SL/NB)——设计书 §7
_CN_HYDRAULIC = CodeSet(
    jurisdiction="CN",
    codes=["SL 191-2008(水工混凝土结构)", "SL 744-2016(水工建筑物荷载)",
           "NB/T 35026-2014(混凝土重力坝)", "SL 265-2016(水闸)", "NB 35047-2015(水电工程抗震)"],
    mandatory=["CN.NBT35026-2014.坝基抗滑稳定", "CN.SL265-2016.水闸抗浮", "CN.SL265-2016.水闸抗滑"],
    review_process="水利部/能源局审查(强条零容忍) + 大坝安全专项",
    note="水工规范包(SL/NB)；扬压力/浪压力/淤沙/冰压力自动进组合(后续)。")


def resolve(country: str, structure_type: str = "building",
            commission: str = "design", na: str = None) -> CodeSet:
    """确定性产出生效规范集。country: CN/EU/JP/US；structure_type: building/gravity_dam/sluice…；
    na: EC 国别 National Annex(如 DE)。"""
    if country.upper() == "CN" and structure_type in _HYDRAULIC:
        return _CN_HYDRAULIC
    cs = _TABLE.get(country.upper())
    if cs is None:
        raise ValueError(f"未知辖区: {country}（已支持 {', '.join(_TABLE)}）")
    if cs.jurisdiction == "EU" and na and na in NDP:
        cs = CodeSet(cs.jurisdiction, cs.codes, cs.mandatory, cs.review_process,
                     ndp=NDP[na], note=cs.note + f" National Annex={na}.")
    return cs


def list_jurisdictions():
    return list(_TABLE.keys())
