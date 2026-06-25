"""
梁设计编排器 — 把受弯、受剪、构造、选筋串成单构件完整设计。

对每个控制截面：受弯配筋 → 最小/最大配筋率校核 → 选纵筋。
对剪力：受剪配筋 → 最小配箍率 + 最大间距 → 选箍筋。
所有过程累积到追溯日志，供计算书使用。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from . import rebar as rb
from .model import Beam
from .codes import gb50010_beam as gb
from .trace import TraceLog, Basis


@dataclass
class SectionDesign:
    location: str
    M: float
    As_req: float
    As_min: float
    As_governing: float      # max(计算, 构造最小)
    bars: rb.BarChoice
    As_prov: float
    doubly: bool
    As_comp_req: float
    comp_bars: Optional[rb.BarChoice]
    flexure_ok: bool
    max_ok: bool
    note: str
    log: TraceLog


@dataclass
class ShearDesign:
    V: float
    Asv_s_req: float
    stirrup: str          # 例如 "D8@200(2)"
    Asv_s_prov: float
    rho_sv: float
    rho_sv_min: float
    smax: float
    ok: bool
    note: str
    log: TraceLog


@dataclass
class BeamDesignResult:
    beam: Beam
    sections: List[SectionDesign] = field(default_factory=list)
    shear: Optional[ShearDesign] = None
    overall_ok: bool = True


def design_beam(beam: Beam) -> BeamDesignResult:
    sec = beam.section
    b, h = sec.b, sec.h
    cg = sec.concrete
    rg = beam.main_rebar_grade
    sg = beam.stirrup_grade
    result = BeamDesignResult(beam=beam)

    # ---- 受弯：逐控制截面 ----
    Vmax = 0.0
    for f in beam.forces:
        tension_bottom = f.M >= 0
        a_s = sec.as_bottom if tension_bottom else sec.as_top
        fl = gb.design_flexure(b, h, abs(f.M), cg, rg,
                               a_s=a_s, a_s_prime=sec.as_top)
        h0 = h - a_s
        As_min, rho_min = gb.min_tension_area(b, h, cg, rg)
        fl.log.step(title="最小配筋率校核", clause="8.5.1",
                    basis=Basis.CONSTRUCTION,
                    expression="ρmin = max(0.20%, 0.45·ft/fy);  As,min = ρmin·b·h",
                    substitution=f"ρmin={rho_min*100:.3f}%, As,min={As_min:.1f} mm²",
                    result=("计算控制" if fl.As >= As_min else "构造最小配筋控制"))
        As_gov = max(fl.As, As_min)
        max_ok, As_max = gb.max_tension_check(As_gov, b, h0, cg, rg)
        bars = rb.select_bars(As_gov, b)
        fl.log.step(title="选纵筋", clause="9.2.1",
                    basis=Basis.CONSTRUCTION,
                    substitution=f"需 As={As_gov:.1f} mm² → 选 {bars.label()}",
                    result=f"实配 As={bars.As:.1f} mm²（超配 {(bars.As/As_gov-1)*100:.1f}%）")
        comp_bars = None
        if fl.doubly and fl.As_comp > 0:
            comp_bars = rb.select_bars(fl.As_comp, b)

        note = []
        if not fl.ok:
            note.append(fl.message)
            result.overall_ok = False
        if not max_ok:
            note.append(f"超筋(As>{As_max:.0f})，建议加大截面")
            result.overall_ok = False
        result.sections.append(SectionDesign(
            location=f.location, M=f.M, As_req=fl.As, As_min=As_min,
            As_governing=As_gov, bars=bars, As_prov=bars.As,
            doubly=fl.doubly, As_comp_req=fl.As_comp, comp_bars=comp_bars,
            flexure_ok=fl.ok, max_ok=max_ok,
            note="；".join(note), log=fl.log))
        Vmax = max(Vmax, abs(f.V))

    # ---- 受剪：取最大剪力 ----
    if beam.forces:
        sh = gb.design_shear(b, h, Vmax, cg, sg, a_s=sec.as_bottom)
        log = sh.log
        sd_ok = sh.ok
        if not sh.section_ok:
            result.overall_ok = False
            result.shear = ShearDesign(
                V=Vmax, Asv_s_req=0, stirrup="—", Asv_s_prov=0, rho_sv=0,
                rho_sv_min=0, smax=0, ok=False, note=sh.message, log=log)
        else:
            rho_min = gb.min_stirrup_ratio(cg, sg)
            V_exceeds = not sh.only_constructional
            smax = gb.max_stirrup_spacing(h, V_exceeds)
            # 选箍筋：2 肢，先定直径再定间距
            legs = 2
            chosen = None
            for d in rb.STIRRUP_DIAMETERS:
                Asv = legs * rb.area(d)
                # 计算需求间距
                if sh.Asv_s > 0:
                    s_calc = Asv / sh.Asv_s
                else:
                    s_calc = 1e9
                # 最小配箍率限制的间距
                s_rho = Asv / (rho_min * b)
                s = min(s_calc, s_rho, smax)
                # 取 25 的倍数向下圆整
                s = max(50, int(s // 25) * 25)
                rho_sv = Asv / (b * s)
                if rho_sv >= rho_min and s <= smax:
                    chosen = (d, s, Asv, rho_sv)
                    break
            if chosen is None:
                d = rb.STIRRUP_DIAMETERS[-1]
                s = max(50, int(smax // 25) * 25)
                Asv = legs * rb.area(d)
                rho_sv = Asv / (b * s)
                chosen = (d, s, Asv, rho_sv)
            d, s, Asv, rho_sv = chosen
            log.step(title="最小配箍率", clause="9.2.9", basis=Basis.CONSTRUCTION,
                     expression="ρsv,min = 0.24·ft/fyv",
                     substitution=f"ρsv,min={rho_min*100:.3f}%",
                     result=f"最大箍筋间距 smax={smax} mm")
            stirrup_label = f"D{int(d)}@{int(s)}({legs})"
            log.step(title="选箍筋", clause="9.2.9", basis=Basis.CONSTRUCTION,
                     substitution=f"{legs}肢D{int(d)}, s={int(s)}mm",
                     result=f"{stirrup_label}, 实配 ρsv={rho_sv*100:.3f}% "
                            f"({'满足' if rho_sv>=rho_min else '不足'})")
            result.shear = ShearDesign(
                V=Vmax, Asv_s_req=sh.Asv_s, stirrup=stirrup_label,
                Asv_s_prov=Asv / s, rho_sv=rho_sv, rho_sv_min=rho_min,
                smax=smax, ok=(rho_sv >= rho_min), note="", log=log)
    return result
