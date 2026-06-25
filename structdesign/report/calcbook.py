"""
结构计算书自动生成 — 把带追溯的设计结果渲染成 markdown。

每个数字都附“[依据类型 · 规范条文]”，满足施工图审查对可追溯性的要求。
"""
from __future__ import annotations
from datetime import date
from ..design_beam import BeamDesignResult


def beam_calcbook(result: BeamDesignResult, project: str = "示例工程") -> str:
    beam = result.beam
    sec = beam.section
    L = []
    L.append(f"# 结构计算书 — 梁 {beam.name}")
    L.append("")
    L.append(f"工程名称：{project}　　日期：{date.today().isoformat()}")
    L.append(f"依据规范：GB 50010-2010(2015年版) 混凝土结构设计规范")
    L.append("")
    L.append("> 本计算书由 structdesign 自动生成。求解依据优先级：规范公式 → 有限元 → 工程方法；")
    L.append("> 本梁全部计算项均有规范闭式公式，故全部采用规范公式，每步标注条文出处。")
    L.append("")

    # 构件信息
    L.append("## 一、构件信息")
    L.append("")
    L.append(f"- 截面：b×h = {sec.b}×{sec.h} mm，混凝土 {sec.concrete}")
    L.append(f"- 纵筋：{beam.main_rebar_grade}；箍筋：{beam.stirrup_grade}")
    L.append(f"- 计算跨度：{beam.span} mm；保护层参数 a_s={sec.as_bottom}/a_s'={sec.as_top} mm")
    if beam.seismic_grade:
        L.append(f"- 抗震等级：{beam.seismic_grade}")
    L.append("")

    # 受弯
    L.append("## 二、正截面受弯承载力计算")
    for i, sd in enumerate(result.sections, 1):
        L.append("")
        L.append(f"### 2.{i} 控制截面：{sd.location}（M = {sd.M} kN·m）")
        L.append("")
        L.append(sd.log.render())
        L.append("")
        status = "✔ 通过" if (sd.flexure_ok and sd.max_ok) else "✗ 不满足"
        L.append(f"**配筋结论：{sd.bars.label()}（As={sd.bars.As:.0f} mm² ≥ 需求 {sd.As_governing:.0f} mm²）　{status}**")
        if sd.doubly and sd.comp_bars:
            L.append("")
            L.append(f"受压钢筋：{sd.comp_bars.label()}（As'={sd.comp_bars.As:.0f} mm²）")
        if sd.note:
            L.append("")
            L.append(f"> ⚠ {sd.note}")

    # 受剪
    if result.shear:
        sh = result.shear
        L.append("")
        L.append("## 三、斜截面受剪承载力计算")
        L.append("")
        L.append(f"取最大剪力设计值 V = {sh.V} kN")
        L.append("")
        L.append(sh.log.render())
        L.append("")
        status = "✔ 通过" if sh.ok else "✗ 不满足"
        if sh.stirrup != "—":
            L.append(f"**箍筋结论：{sh.stirrup}　实配 ρsv={sh.rho_sv*100:.3f}% ≥ ρsv,min={sh.rho_sv_min*100:.3f}%　{status}**")
        else:
            L.append(f"**受剪结论：{sh.note}　{status}**")

    # 汇总
    L.append("")
    L.append("## 四、配筋汇总")
    L.append("")
    L.append("| 截面 | 弯矩(kN·m) | 计算As(mm²) | 实配纵筋 | 实配As(mm²) |")
    L.append("|------|-----------|------------|---------|------------|")
    for sd in result.sections:
        L.append(f"| {sd.location} | {sd.M} | {sd.As_governing:.0f} | {sd.bars.label()} | {sd.bars.As:.0f} |")
    if result.shear and result.shear.stirrup != "—":
        L.append("")
        L.append(f"箍筋：{result.shear.stirrup}")
    L.append("")
    L.append(f"**总体结论：{'✔ 全部满足规范要求' if result.overall_ok else '✗ 存在不满足项，详见上文'}**")
    L.append("")
    return "\n".join(L)
