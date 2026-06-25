"""
USM 统一结构模型（骨架）。

这是内核与外部建模软件之间的“防火墙”：所有外部软件(ETABS/YJK/PKPM…)
通过适配器读写 USM，L3 以上内核只认 USM。本里程碑先定义梁设计所需的最小字段。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from . import materials


@dataclass
class RectSection:
    """矩形截面 (mm)。"""
    b: float          # 截面宽度
    h: float          # 截面高度
    concrete: str = "C30"
    as_bottom: float = 40.0   # 下部受拉钢筋合力点到底边距离 a_s
    as_top: float = 40.0      # 上部钢筋合力点到顶边距离 a_s'

    def h0(self, tension_at_bottom: bool = True) -> float:
        """有效高度 h0 = h - a_s。"""
        a = self.as_bottom if tension_at_bottom else self.as_top
        return self.h - a

    @property
    def conc(self) -> materials.Concrete:
        return materials.concrete(self.concrete)


@dataclass
class BeamForces:
    """梁某控制截面的设计内力（已是组合包络后的设计值）。

    本里程碑直接接收设计内力；阶段 0 的“工况→组合→包络→能力设计调整”
    数据流将在此之前生成这些值。
    """
    M: float          # 弯矩设计值 (kN·m)，正=下部受拉
    V: float          # 剪力设计值 (kN)
    location: str = "跨中"   # 截面位置标识(跨中/支座等)


@dataclass
class Beam:
    """梁构件 (USM)。"""
    name: str
    section: RectSection
    span: float = 6000.0                  # 计算跨度 (mm)
    main_rebar_grade: str = "HRB400"      # 纵筋牌号
    stirrup_grade: str = "HPB300"         # 箍筋牌号
    seismic_grade: Optional[str] = None   # 抗震等级(一/二/三/四级)，None=非抗震
    # 该构件的若干控制截面内力
    forces: list = field(default_factory=list)

    def add_forces(self, f: BeamForces) -> "Beam":
        self.forces.append(f)
        return self


@dataclass
class ColumnForces:
    """柱某控制截面的设计内力（组合后设计值）。"""
    N: float          # 轴力设计值 (kN, 压为正)
    M: float          # 弯矩设计值 (kN·m)
    V: float = 0.0    # 剪力设计值 (kN)
    location: str = "柱底"


@dataclass
class Column:
    """柱构件 (USM)。"""
    name: str
    section: RectSection
    height: float = 3600.0                 # 层高 (mm)
    main_rebar_grade: str = "HRB400"
    stirrup_grade: str = "HPB300"
    seismic_grade: Optional[str] = None    # 抗震等级(一/二/三/四级)
    forces: list = field(default_factory=list)

    def add_forces(self, f: "ColumnForces") -> "Column":
        self.forces.append(f)
        return self
