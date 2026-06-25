"""
材料库 — GB 50010-2010(2015年版) 混凝土与钢筋设计指标。

所有强度单位 N/mm² (MPa)。数值取自规范表 4.1.4 (混凝土) 与表 4.2.3 (钢筋)。
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Concrete:
    grade: str
    fc: float    # 轴心抗压强度设计值
    ft: float    # 轴心抗拉强度设计值
    Ec: float    # 弹性模量
    fcuk: float  # 立方体抗压强度标准值 (=等级数字)

    @property
    def alpha1(self) -> float:
        """受压区等效矩形应力图系数 α1 (规范 6.2.6)。≤C50 取 1.0，C80 取 0.94，线性内插。"""
        if self.fcuk <= 50:
            return 1.0
        if self.fcuk >= 80:
            return 0.94
        return 1.0 + (0.94 - 1.0) * (self.fcuk - 50) / (80 - 50)

    @property
    def beta1(self) -> float:
        """受压区高度系数 β1 (规范 6.2.6)。≤C50 取 0.8，C80 取 0.74，线性内插。"""
        if self.fcuk <= 50:
            return 0.8
        if self.fcuk >= 80:
            return 0.74
        return 0.8 + (0.74 - 0.8) * (self.fcuk - 50) / (80 - 50)

    @property
    def beta_c(self) -> float:
        """混凝土强度影响系数 βc (规范 6.3.1)。≤C50 取 1.0，C80 取 0.8，线性内插。"""
        if self.fcuk <= 50:
            return 1.0
        if self.fcuk >= 80:
            return 0.8
        return 1.0 + (0.8 - 1.0) * (self.fcuk - 50) / (80 - 50)

    @property
    def epsilon_cu(self) -> float:
        """非均匀受压时混凝土极限压应变 εcu (规范 6.2.1)。"""
        if self.fcuk <= 50:
            return 0.0033
        return min(0.0033, 0.0033 - (self.fcuk - 50) * 1e-5)


@dataclass(frozen=True)
class Rebar:
    grade: str
    fy: float    # 抗拉强度设计值
    fyc: float   # 抗压强度设计值
    Es: float    # 弹性模量

    def fyv(self) -> float:
        """用作箍筋时的抗拉强度设计值：受剪计算中不大于 360 (规范 6.3.4 条文说明)。"""
        return min(self.fy, 360.0)


# --- 混凝土等级表 (设计值) ---
_CONCRETE = {
    "C20": Concrete("C20", 9.6, 1.10, 2.55e4, 20),
    "C25": Concrete("C25", 11.9, 1.27, 2.80e4, 25),
    "C30": Concrete("C30", 14.3, 1.43, 3.00e4, 30),
    "C35": Concrete("C35", 16.7, 1.57, 3.15e4, 35),
    "C40": Concrete("C40", 19.1, 1.71, 3.25e4, 40),
    "C45": Concrete("C45", 21.1, 1.80, 3.35e4, 45),
    "C50": Concrete("C50", 23.1, 1.89, 3.45e4, 50),
    "C55": Concrete("C55", 25.3, 1.96, 3.55e4, 55),
    "C60": Concrete("C60", 27.5, 2.04, 3.60e4, 60),
}

# --- 钢筋牌号表 (设计值)。ξb 见 ksi_b()。---
_REBAR = {
    "HPB300": Rebar("HPB300", 270, 270, 2.10e5),
    "HRB335": Rebar("HRB335", 300, 300, 2.00e5),
    "HRB400": Rebar("HRB400", 360, 360, 2.00e5),
    "HRBF400": Rebar("HRBF400", 360, 360, 2.00e5),
    "RRB400": Rebar("RRB400", 360, 360, 2.00e5),
    "HRB500": Rebar("HRB500", 435, 410, 2.00e5),
    "HRBF500": Rebar("HRBF500", 435, 410, 2.00e5),
}

# 相对界限受压区高度 ξb (规范表 6.2.7-1，有屈服点钢筋)
_XI_B = {
    "HPB300": 0.576,
    "HRB335": 0.550,
    "HRBF335": 0.550,
    "HRB400": 0.518,
    "HRBF400": 0.518,
    "RRB400": 0.518,
    "HRB500": 0.482,
    "HRBF500": 0.482,
}


def concrete(grade: str) -> Concrete:
    g = grade.upper()
    if g not in _CONCRETE:
        raise KeyError(f"未知混凝土等级 {grade}；可用: {list(_CONCRETE)}")
    return _CONCRETE[g]


def rebar(grade: str) -> Rebar:
    g = grade.upper()
    if g not in _REBAR:
        raise KeyError(f"未知钢筋牌号 {grade}；可用: {list(_REBAR)}")
    return _REBAR[g]


def ksi_b(rebar_grade: str) -> float:
    """相对界限受压区高度 ξb (规范 6.2.7)。"""
    g = rebar_grade.upper()
    if g not in _XI_B:
        raise KeyError(f"未知钢筋牌号 {rebar_grade}")
    return _XI_B[g]
