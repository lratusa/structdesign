"""
一键总流程 —— 读参数 → 导荷 → 分析配筋(含P-Δ) → 钢筋表 → 出图 → 计算书。

把全部模块串成单一入口 design_project()。输入规则框架参数 + 楼板荷载 + 地震参数，
输出：BuildingDesign、钢筋表、平法图(SVG/DXF)、截面大样、总钢量，并写计算书。
说明：内核为 2D 平面框架，多/高层结果属**方案级**，最终需三维软件复核+工程师签字。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

from . import loads_takedown as td
from . import rebar as rb
from .frame_spec import SecBox
from .design_building import seismic_closed_loop
from .detailing.schedule import Schedule
from .detailing.grouping import group_rebar
from .drawing.pingfa import BeamPingfa, sym
from .drawing.pingfa_dxf import batch_beams_dxf
from .drawing.section import section_svg


@dataclass
class ProjectParams:
    n_bays: int = 4
    n_stories: int = 6
    bay_w: float = 8000.0
    story_h: float = 3600.0
    floor_area: float = 0.0          # 单层面积(㎡)，仅记录
    dead_kpa: float = 5.0
    live_kpa: float = 2.0
    alpha_max: float = 0.08
    Tg: float = 0.40
    seismic_grade: str = "三级"
    col0: tuple = (500, 500)
    beam0: tuple = (300, 600)
    concrete_col: str = "C40"
    concrete_beam: str = "C30"


@dataclass
class ProjectResult:
    params: ProjectParams
    w_gravity: float
    building: object
    schedule: Schedule
    total_steel_t: float
    steel_per_m2: float
    files: Dict[str, str] = field(default_factory=dict)
    summary: str = ""


def design_project(p: ProjectParams, out_dir: str) -> ProjectResult:
    os.makedirs(out_dir, exist_ok=True)
    # 1) 导荷：楼板面荷载 → 梁线荷载(取梁间距=bay_w 的单向近似)
    q = td.slab_q(p.dead_kpa, p.live_kpa)
    w = td.one_way_udl(q, p.bay_w / 1000.0)      # kN/m = N/mm
    # 2) 分析+配筋+截面自动生长(闭环)
    res = seismic_closed_loop(
        p.n_bays, p.n_stories, p.bay_w, p.story_h,
        lambda: SecBox(*p.col0, p.concrete_col, "column", h_max=1200, seismic_grade=p.seismic_grade),
        lambda: SecBox(*p.beam0, p.concrete_beam, "beam", h_max=1200, seismic_grade=p.seismic_grade),
        w_gravity=w, story_mass=p.floor_area * 1000.0 if p.floor_area else 3e5,
        alpha_max=p.alpha_max, Tg=p.Tg, seismic_grade=p.seismic_grade, h_step=50.0)
    bd = res.final

    # 3) 钢筋表（从配筋估算：梁纵筋按跨长，柱纵筋按层高）
    sc = Schedule()
    sy = sym("HRB400")
    for mid, m in bd.members.items():
        b, h = (int(x) for x in res.final_sections[mid].split("×"))
        if m.kind == "beam":
            bars = rb.select_bars(m.As, b)
            sc.add(mid, "HRB400", bars.d, bars.n, p.bay_w + 800)        # 含锚固
            sc.add(mid + "底", "HRB400", bars.d, max(2, bars.n - 1), p.bay_w + 800)
        else:
            bars = rb.select_bars(m.As / 2, b)
            sc.add(mid, "HRB400", bars.d, bars.n * 2, p.story_h + 600)  # 对称两侧
    total_t = sc.total_mass_kg / 1000.0
    # 含钢量按本榀框架的受荷(tributary)面积：框架长 × 一跨受荷宽 × 层数
    frame_area = (p.n_bays * p.bay_w / 1000.0) * (p.bay_w / 1000.0) * p.n_stories
    steel_per_m2 = sc.total_mass_kg / frame_area if frame_area else 0.0

    # 4) 出图：代表性梁平法图(批量) + 截面大样
    beam_ids = [mid for mid in bd.members if bd.members[mid].kind == "beam"][:8]
    beams = []
    for mid in beam_ids:
        b, h = (int(x) for x in res.final_sections[mid].split("×"))
        m = bd.members[mid]
        sb = rb.select_bars(m.As, b)
        beams.append(BeamPingfa(beam_id=mid, n_span=p.n_bays, b=b, h=h,
                                length_mm=p.bay_w, support_top=sb.label().replace("D", sy),
                                bottom=sb.label().replace("D", sy), top_through="2C20"))
    files = {}
    if beams:
        files["梁平法图_dxf"] = batch_beams_dxf(beams).save(os.path.join(out_dir, "梁平法图.dxf"))
        # 代表梁截面大样
        bb = beams[0]
        sbar = rb.select_bars(bd.members[bb.beam_id].As, bb.b)
        with open(os.path.join(out_dir, "截面大样.svg"), "w", encoding="utf-8") as f:
            f.write(section_svg(bb.b, bb.h, n_top=sbar.n, n_bot=max(2, sbar.n - 1),
                                d_main=sbar.d, n_side=2, title=f"{bb.beam_id} 截面"))
        files["截面大样_svg"] = os.path.join(out_dir, "截面大样.svg")

    # 5) 计算书
    cb = os.path.join(out_dir, "计算书_总.md")
    with open(cb, "w", encoding="utf-8") as f:
        f.write(f"# 结构设计计算书（一键总流程）\n\n")
        f.write(f"规模：{p.n_bays}跨×{p.n_stories}层；单层面积约 {p.floor_area or '—'} ㎡。\n")
        f.write(f"楼板荷载 q=1.3·{p.dead_kpa}+1.5·{p.live_kpa}={q} kN/m² → 梁线荷载 w={w:.1f} kN/m。\n\n")
        f.write(f"地震：αmax={p.alpha_max}, Tg={p.Tg}, {p.seismic_grade}；含 P-Δ。\n\n")
        f.write(f"- 自振周期 T1={bd.T1:.3f}s；基底剪力 {bd.base_shear/1e3:.0f}kN；整体屈曲系数 λcr={bd.stability:.0f}\n")
        f.write(f"- 截面自动生长闭环：{'收敛' if res.converged else '未完全收敛'}（{res.iterations}轮）\n")
        n_bad = sum(0 if m.ok else 1 for m in bd.members.values())
        f.write(f"- 构件总数 {len(bd.members)}，截面不足/超限 {n_bad}\n\n")
        f.write(f"## 用钢量\n\n总用钢约 **{total_t:.1f} t**，含钢量约 **{steel_per_m2:.1f} kg/㎡**"
                f"（仅梁柱纵筋估算，未含箍筋/板/墙）。\n\n")
        f.write("## 钢筋表（节选）\n\n")
        sc2 = Schedule(); sc2.rows = sc.rows[:12]
        f.write(sc2.render_markdown() + "\n\n")
        f.write("> 内核为 2D 平面框架，方案级结果；高层/复杂结构最终须三维软件复核并由注册工程师签字。\n")
    files["计算书_md"] = cb

    n_bad = sum(0 if m.ok else 1 for m in bd.members.values())
    feasible = res.converged and n_bad == 0
    summary = (f"T1={bd.T1:.3f}s 基底剪力={bd.base_shear/1e3:.0f}kN λcr={bd.stability:.0f} "
               f"用钢≈{total_t:.1f}t({steel_per_m2:.1f}kg/㎡) 构件{len(bd.members)}个 "
               f"{'✔方案可行' if feasible else f'✗不足构件{n_bad}个(需加大截面/设剪力墙)'} {res.iterations}轮")
    return ProjectResult(params=p, w_gravity=w, building=bd, schedule=sc,
                         total_steel_t=total_t, steel_per_m2=steel_per_m2,
                         files=files, summary=summary)
