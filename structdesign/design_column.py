"""
柱设计编排器 —— 对称配筋偏心受压 + 轴压比 + 最小配筋率 + 选筋。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from . import rebar as rb
from .model import Column
from .codes import gb50010_column as gc
from .trace import TraceLog, Basis


@dataclass
class ColumnDesignResult:
    column: Column
    As_total_req: float = 0.0
    As_total_min: float = 0.0
    As_total_gov: float = 0.0
    bars_per_side: Optional[rb.BarChoice] = None
    As_total_prov: float = 0.0
    eccentric: str = ""
    axial_ratio: float = 0.0
    axial_limit: float = 0.0
    axial_ok: bool = True
    ok: bool = True
    note: str = ""
    log: TraceLog = field(default_factory=TraceLog)


def design_column(col: Column) -> ColumnDesignResult:
    sec = col.section
    b, h = sec.b, sec.h
    cg, rg = sec.concrete, col.main_rebar_grade
    res = ColumnDesignResult(column=col, log=TraceLog())

    # 取最不利内力：对每个内力算配筋，取最大 As
    worst = None
    Nmax = 0.0
    for f in col.forces:
        r = gc.design_column_symmetric(b, h, f.N, f.M, cg, rg, a_s=sec.as_bottom)
        if worst is None or r.As_total > worst.As_total:
            worst = r
        Nmax = max(Nmax, f.N)
    if worst is None:
        res.ok = False
        res.note = "无内力输入"
        return res
    res.log = worst.log
    res.eccentric = worst.eccentric
    res.As_total_req = worst.As_total

    # 轴压比（取最大轴力）
    mu, limit, axial_ok = gc.axial_compression_ratio(Nmax, b, h, cg, col.seismic_grade)
    res.axial_ratio, res.axial_limit, res.axial_ok = mu, limit, axial_ok
    res.log.step(title="轴压比校核", clause="GB 50011 6.3.6",
                 basis=Basis.CODE_FORMULA,
                 expression="μN = N/(fc·A)",
                 substitution=f"μN={mu:.3f}, 限值={limit}",
                 result=("满足" if axial_ok else "超限，需加大截面或提高混凝土等级"))

    # 最小配筋率
    As_min, rho_min = gc.column_min_reinforcement(b, h, col.seismic_grade)
    res.As_total_min = As_min
    res.log.step(title="柱全部纵筋最小配筋率", clause="GB 50011 6.3.7",
                 basis=Basis.CONSTRUCTION,
                 substitution=f"ρmin={rho_min*100:.2f}%, As,min(全部)={As_min:.0f} mm²",
                 result=("计算控制" if worst.As_total >= As_min else "构造最小配筋控制"))
    As_gov = max(worst.As_total, As_min)
    res.As_total_gov = As_gov

    # 选筋（对称，单侧 As_gov/2）
    bars = rb.select_bars(As_gov / 2.0, b)
    res.bars_per_side = bars
    res.As_total_prov = bars.As * 2
    res.log.step(title="选纵筋(对称,每侧)", clause="9.3.1",
                 basis=Basis.CONSTRUCTION,
                 substitution=f"每侧需 {As_gov/2:.0f} mm² → 每侧 {bars.label()}",
                 result=f"全截面 2×{bars.label()}, 实配 As={res.As_total_prov:.0f} mm²")

    if not axial_ok:
        res.ok = False
        res.note = "轴压比超限"
    return res
