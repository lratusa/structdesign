"""
荷载工况 / 组合 / 包络 —— GB 50009-2012(2018局部修订) + GB 50011。

把各工况(恒G/活Q/风W/地震E)的构件内力，按规范分项系数组合，再取包络得到
设计内力。这是阶段0数据流的核心：配筋内核拿到的"设计内力"由此产生。

分项系数（2018修订后）：γG=1.3(不利)/1.0(有利)，γQ=1.5，γW=1.5；
组合值系数 ψw=0.6，ψq=0.7；地震组合 γG=1.3, γEh=1.4，重力代表值 GE=G+0.5Q。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# 工况标识
G, Q, W, E = "G", "Q", "W", "E"


@dataclass
class CaseForces:
    """单工况下某构件控制截面的标准值内力。"""
    M: float = 0.0   # kN·m
    V: float = 0.0   # kN
    N: float = 0.0   # kN (压为正)


def _lin(cases: Dict[str, CaseForces], coeffs: Dict[str, float]) -> CaseForces:
    M = sum(coeffs.get(k, 0) * c.M for k, c in cases.items())
    V = sum(coeffs.get(k, 0) * c.V for k, c in cases.items())
    N = sum(coeffs.get(k, 0) * c.N for k, c in cases.items())
    return CaseForces(M, V, N)


def basic_combinations(cases: Dict[str, CaseForces]) -> List[Tuple[str, CaseForces]]:
    """持久/短暂工况基本组合（非抗震）。"""
    has_w = W in cases
    combos = [("1.3G+1.5Q", _lin(cases, {G: 1.3, Q: 1.5}))]
    if has_w:
        combos.append(("1.3G+1.5Q+1.5×0.6W", _lin(cases, {G: 1.3, Q: 1.5, W: 0.9})))
        combos.append(("1.3G+1.5×0.7Q+1.5W", _lin(cases, {G: 1.3, Q: 1.05, W: 1.5})))
        # 恒载有利（抗倾覆/抗浮类）
        combos.append(("1.0G+1.5W", _lin(cases, {G: 1.0, W: 1.5})))
    return combos


def seismic_combinations(cases: Dict[str, CaseForces]) -> List[Tuple[str, CaseForces]]:
    """地震设计状况组合（水平地震为主）。GE=G+0.5Q。"""
    if E not in cases:
        return []
    # 1.3·GE ± 1.4·E ；GE 用 {G:1, Q:0.5}
    out = []
    out.append(("1.3(G+0.5Q)+1.4E", _lin(cases, {G: 1.3, Q: 0.65, E: 1.4})))
    out.append(("1.3(G+0.5Q)-1.4E", _lin(cases, {G: 1.3, Q: 0.65, E: -1.4})))
    out.append(("1.0(G+0.5Q)+1.4E", _lin(cases, {G: 1.0, Q: 0.5, E: 1.4})))
    return out


@dataclass
class ForceEnvelope:
    M_pos: float = 0.0   # 最大正弯矩
    M_neg: float = 0.0   # 最小(最负)弯矩
    V_max: float = 0.0   # 最大剪力绝对值
    N_max: float = 0.0   # 最大轴力(压)
    N_min: float = 0.0   # 最小轴力(可能拉)
    combos: List[Tuple[str, CaseForces]] = field(default_factory=list)


def envelope(cases: Dict[str, CaseForces], seismic: bool = False) -> ForceEnvelope:
    """对所有适用组合取包络。"""
    combos = basic_combinations(cases)
    if seismic:
        combos = combos + seismic_combinations(cases)
    env = ForceEnvelope(combos=combos)
    env.M_pos = max((c.M for _, c in combos), default=0.0)
    env.M_neg = min((c.M for _, c in combos), default=0.0)
    env.V_max = max((abs(c.V) for _, c in combos), default=0.0)
    env.N_max = max((c.N for _, c in combos), default=0.0)
    env.N_min = min((c.N for _, c in combos), default=0.0)
    return env
