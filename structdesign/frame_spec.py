"""
软件中立的框架描述（USM 子集）+ 内力数据契约。

所有分析引擎（内置有限元 / ETABS / YJK）都消费 FrameSpec、产出同一套 MemberForces。
这样闭环与配筋内核完全不关心底层用哪个引擎算。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from . import materials
from .analysis.frame2d import FrameModel, Node, Member, NodalLoad


@dataclass
class SecBox:
    """构件截面 + 建筑可行域上限。"""
    b: float
    h: float
    concrete: str = "C30"
    kind: str = "beam"          # 'beam' or 'column'
    h_max: float = 1200.0
    b_max: float = 1000.0
    seismic_grade: Optional[str] = "二级"

    @property
    def A(self): return self.b * self.h
    @property
    def I(self): return self.b * self.h ** 3 / 12.0
    @property
    def E(self): return materials.concrete(self.concrete).Ec


@dataclass
class FrameSpec:
    nodes: Dict[str, Tuple[float, float, Tuple[bool, bool, bool]]]
    members: Dict[str, Tuple[str, str, SecBox, float]]   # id -> (ni,nj,sec,w[N/mm])
    loads: List[NodalLoad] = field(default_factory=list)


@dataclass
class MemberForces:
    """统一内力契约。任何引擎都须按此返回。单位：N, N·mm。"""
    Mi: float = 0.0
    Mj: float = 0.0
    M_mid: float = 0.0
    Vi: float = 0.0
    Vj: float = 0.0
    N_axial: float = 0.0   # 压为正


def build_model(spec: FrameSpec) -> FrameModel:
    """FrameSpec → 内置有限元模型。"""
    m = FrameModel()
    for nid, (x, y, r) in spec.nodes.items():
        m.add_node(Node(nid, x, y, r))
    for mid, (ni, nj, sec, w) in spec.members.items():
        m.add_member(Member(mid, ni, nj, sec.E, sec.A, sec.I, w=w))
    for ld in spec.loads:
        m.add_load(ld)
    return m
