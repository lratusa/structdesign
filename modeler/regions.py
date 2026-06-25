"""地区标准体系 —— 国标(GB) + 地方标准(地标)。

不同地区的设计参数（设防烈度→αmax/Tg、基本风压 w0、基本雪压、标准冻深）及适用规范不同。
本模块用 registry 模式管理：国标(national)为基线，各城市为一条 RegionStandard 条目。
**加新城市 = 在 REGIONS 里加一条**，无需改其它代码。

选定地区后 `apply_region(project, key)` 把该地区的参数填入 project（地震/风），
计算书引用该地区的 `codes`（国标 + 地标）。

诚实边界：地区参数为该市常见取值（按现行规范/区划图）；**具体工程的设防烈度、设计地震分组、
场地类别、基本风/雪压须按工程所在地最新区划图与地勘报告核定**，不能仅凭城市名。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

GB_CODES = [
    "《建筑结构荷载规范》GB 50009-2012",
    "《混凝土结构设计规范》GB 50010-2010(2015年版)",
    "《建筑抗震设计规范》GB 50011-2010(2016年版)",
    "《高层建筑混凝土结构技术规程》JGJ 3-2010",
]


@dataclass
class RegionStandard:
    key: str
    name: str
    intensity: str             # 设防烈度/加速度/分组 描述
    alpha_max: float           # 多遇地震 αmax
    Tg: float                  # 特征周期(常见场地，s)
    w0: float                  # 基本风压 kN/m²(50年)
    terrain: str               # 默认地面粗糙度
    snow0: float = 0.0         # 基本雪压 kN/m²(预留，雪荷载功能后用)
    frost_depth: float = 0.0   # 标准冻结深度 mm(预留，基础埋深用)
    extra_codes: List[str] = field(default_factory=list)   # 该地区附加地标
    notes: str = ""

    @property
    def codes(self) -> List[str]:
        return GB_CODES + list(self.extra_codes)


REGIONS: Dict[str, RegionStandard] = {
    "national": RegionStandard(
        key="national", name="国标(GB·通用)",
        intensity="按所在地地震动参数区划图", alpha_max=0.16, Tg=0.45,
        w0=0.40, terrain="B",
        notes="全国通用，地震/风/雪参数须按工程所在地区划图与规范取值。"),
    "beijing": RegionStandard(
        key="beijing", name="北京",
        intensity="8度(0.20g)·设计地震分组第二组(城区常见)", alpha_max=0.16, Tg=0.40,
        w0=0.45, terrain="C", snow0=0.40, frost_depth=800,
        extra_codes=["《北京地区建筑地基基础勘察设计规范》DBJ 11-501-2009(2016年版)"],
        notes="北京城区常见取值：抗震8度0.20g第二组、II类场地 Tg=0.40s、基本风压0.45、"
              "基本雪压0.40、标准冻深约0.8m。具体须按区划图与地勘核定；山区/近郊烈度分组可能不同。"),
}


def list_regions() -> List[RegionStandard]:
    return list(REGIONS.values())


def get_region(key: str) -> RegionStandard:
    return REGIONS.get(key, REGIONS["national"])


def apply_region(project, key: str) -> str:
    """把地区标准参数填入 project（地震 αmax/Tg、风 w0/地面粗糙度），返回中文摘要。"""
    r = get_region(key)
    project.region = r.key
    project.seismic.alpha_max = r.alpha_max
    project.seismic.Tg = r.Tg
    project.wind.w0 = r.w0
    project.wind.terrain = r.terrain
    return (f"已套用「{r.name}」地区标准：αmax={r.alpha_max}、Tg={r.Tg}s、基本风压 w0={r.w0}、"
            f"地面粗糙度{r.terrain}。适用规范含 {len(r.codes)} 部（国标+地标）。{r.notes}")
