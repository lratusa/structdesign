"""
真实外层闭环 —— 截面自动生长 + 重分析 + 内力重分布。

分析引擎可插拔：默认用内置 2D 有限元；传入 EtabsAnalyzer/YjkAnalyzer 即切换，
闭环逻辑不变。这是把 PKPM/YJK "改截面→人工点重算→看是否过" 自动化的核心。
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import materials
from .codes import gb50010_column as gc
from .codes import gb50010_beam as gb
# 中立模型 + 默认引擎
from .frame_spec import SecBox, FrameSpec, MemberForces, build_model  # noqa: F401 (re-export)
from .analyzer.internal import InternalFrameAnalyzer

# 向后兼容旧 import（test_frame_loop 用过 _build）
_build = build_model


@dataclass
class LoopResult:
    converged: bool
    iterations: int
    engine: str = ""
    history: List[str] = field(default_factory=list)
    final_sections: Dict[str, str] = field(default_factory=dict)
    final_forces: Dict[str, str] = field(default_factory=dict)
    reinforcement: Dict[str, str] = field(default_factory=dict)


def closed_loop_design(spec: FrameSpec, analyzer=None,
                       h_step=100.0, max_iter=30) -> LoopResult:
    """外层闭环：分析→校核→生长截面(限步长)→重分析，直到收敛。

    analyzer: 任意实现 .analyze(spec)->{id:MemberForces} 的引擎；None=内置有限元。
    """
    if analyzer is None:
        analyzer = InternalFrameAnalyzer()
    res = LoopResult(converged=False, iterations=0, engine=getattr(analyzer, "name", "?"))

    for it in range(1, max_iter + 1):
        res.iterations = it
        forces = analyzer.analyze(spec)
        changed = False
        notes = []
        for mid, (ni, nj, sec, w) in spec.members.items():
            fr = forces[mid]
            if sec.kind == "column":
                N_kn = abs(fr.N_axial) / 1e3
                mu, limit, ok = gc.axial_compression_ratio(N_kn, sec.b, sec.h, sec.concrete, sec.seismic_grade)
                notes.append(f"{mid}:N={N_kn:.0f}kN,μN={mu:.3f}(限{limit})")
                if not ok and sec.h < sec.h_max:
                    fc = materials.concrete(sec.concrete).fc
                    A_req = N_kn * 1e3 / (limit * fc)
                    h_target = A_req / sec.b
                    new_h = min(sec.h + h_step, sec.h_max, _ceil50(max(h_target, sec.h)))
                    if new_h > sec.h:
                        sec.h = new_h; changed = True
            else:
                M_kn = max(abs(fr.M_mid), abs(fr.Mi), abs(fr.Mj)) / 1e6
                fl = gb.design_flexure(sec.b, sec.h, M_kn, sec.concrete, "HRB400", a_s=40)
                notes.append(f"{mid}:M={M_kn:.0f}kNm,{'双筋' if fl.doubly else '单筋'}")
                if (fl.doubly or not fl.ok) and sec.h < sec.h_max:
                    new_h = min(sec.h + h_step, sec.h_max)
                    if new_h > sec.h:
                        sec.h = new_h; changed = True
        res.history.append(f"第{it}轮: " + "; ".join(notes) + ("  → 生长截面重算" if changed else "  → 收敛"))
        if not changed:
            res.converged = True
            break

    # 收敛后输出
    forces = analyzer.analyze(spec)
    for mid, (ni, nj, sec, w) in spec.members.items():
        fr = forces[mid]
        res.final_sections[mid] = f"{sec.b:.0f}×{sec.h:.0f} {sec.concrete}"
        if sec.kind == "column":
            N_kn = abs(fr.N_axial) / 1e3
            mu, limit, ok = gc.axial_compression_ratio(N_kn, sec.b, sec.h, sec.concrete, sec.seismic_grade)
            res.final_forces[mid] = f"N={N_kn:.0f}kN, μN={mu:.3f}{'✔' if ok else '✗'}"
            cr = gc.design_column_symmetric(sec.b, sec.h, N_kn, abs(fr.Mi)/1e6, sec.concrete, "HRB400")
            As_min, _ = gc.column_min_reinforcement(sec.b, sec.h, sec.seismic_grade)
            res.reinforcement[mid] = f"纵筋 As={max(cr.As_total,As_min):.0f}mm²({cr.eccentric})"
        else:
            M_kn = max(abs(fr.M_mid), abs(fr.Mi), abs(fr.Mj)) / 1e6
            fl = gb.design_flexure(sec.b, sec.h, M_kn, sec.concrete, "HRB400", a_s=40)
            As_min, _ = gb.min_tension_area(sec.b, sec.h, sec.concrete, "HRB400")
            res.final_forces[mid] = f"M={M_kn:.0f}kNm{'(双筋)' if fl.doubly else ''}"
            res.reinforcement[mid] = f"受弯 As={max(fl.As,As_min):.0f}mm²"
    return res


def _ceil50(x):
    return math.ceil(x / 50.0) * 50.0
