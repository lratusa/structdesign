"""生成式方案比选（设计书 §6.2）——N 个结构方案分支 → 多目标 Pareto 前沿。

给定截面边界，生成若干方案(每个方案 = 一个 SSM branch)，各自跑真实分析内核，
输出多目标指标(用钢量 / 混凝土量=造价代理 / 规范是否满足 / 层间位移角 / 周期比)，
标出 **Pareto 前沿**(非受支配方案)与**推荐方案**(满足全部规范且用钢量最小)。

玻璃盒：每个方案的判定来自确定性分析+规范引擎；比选只排序不替工程师拍板。
"""
from __future__ import annotations
import copy
import math
import os
import tempfile
from .ssm import SSMRepo, ssm_from_project


def _apply_sections(project, col_bh, beam_bh):
    """把方案截面套到所有标准层的柱/梁上(返回新 project，不改原对象)。"""
    p = copy.deepcopy(project)
    cb, ch = col_bh
    bb, bh = beam_bh
    for fl in [p.floor, *p.floors.values()]:
        for c in fl.columns:
            c.b, c.h = cb, ch
        for b in fl.beams:
            b.b, b.h = bb, bh
    return p


def _concrete_m3(project) -> float:
    """混凝土体量代理(m³)：柱按总高、梁按跨长×层数。"""
    zs = project.elevations()
    H = (zs[-1] - zs[0]) / 1000.0 if len(zs) > 1 else 3.6
    nfl = project.total_floors()
    fl = project.floor
    col = sum((c.b / 1000.0) * (c.h / 1000.0) for c in fl.columns) * H
    beam = sum((b.b / 1000.0) * (b.h / 1000.0)
               * (math.hypot(b.x2 - b.x1, b.y2 - b.y1) / 1000.0) for b in fl.beams) * nfl
    return col + beam


def evaluate_scheme(project, name, col_bh, beam_bh, repo=None, out_dir=None) -> dict:
    """单方案评估：建 SSM 分支 + 跑分析 + 收集多目标指标。"""
    from modeler.run.analyze import analyze, ModelUnstableError
    p = _apply_sections(project, col_bh, beam_bh)
    if repo is not None:
        repo.branch(name)
        repo.commit(ssm_from_project(p, getattr(p, "jurisdiction", "CN")),
                    f"方案 {name}", "scheme-gen", branch=name)
    od = out_dir or tempfile.mkdtemp(prefix="scheme_")
    try:
        r = analyze(p, od, light=True)
    except ModelUnstableError as e:
        return {"name": name, "col": col_bh, "beam": beam_bh,
                "feasible": False, "reason": f"模型不稳定: {e}",
                "steel_t": float("inf"), "concrete_m3": _concrete_m3(p)}
    feasible = (r.n_bad == 0) and math.isfinite(r.period_ratio)
    return {
        "name": name, "col": col_bh, "beam": beam_bh,
        "feasible": feasible,
        "n_bad": r.n_bad, "n_members": r.n_members,
        "steel_t": float(r.total_steel_t),
        "concrete_m3": round(_concrete_m3(p), 2),
        "drift_x": r.drift_x, "period_ratio": r.period_ratio,
        "reason": "" if feasible else f"{r.n_bad} 个构件不满足规范",
    }


def _dominates(a, b) -> bool:
    """a 支配 b：a 两目标(用钢量、混凝土量)均 ≤ b 且至少一项 <（均为可行方案）。"""
    le = a["steel_t"] <= b["steel_t"] + 1e-9 and a["concrete_m3"] <= b["concrete_m3"] + 1e-9
    lt = a["steel_t"] < b["steel_t"] - 1e-9 or a["concrete_m3"] < b["concrete_m3"] - 1e-9
    return le and lt


def compare_schemes(project, variants) -> dict:
    """variants: [(name, (col_b,col_h), (beam_b,beam_h)), ...] → 比选结果 + Pareto 前沿 + 推荐。"""
    repo = SSMRepo()
    schemes = [evaluate_scheme(project, n, c, b, repo=repo) for (n, c, b) in variants]
    feas = [s for s in schemes if s["feasible"]]
    # Pareto 前沿：可行方案中不被任何其它可行方案支配者
    pareto = [s for s in feas if not any(_dominates(o, s) for o in feas if o is not s)]
    # 推荐：可行方案里用钢量最小(并列取混凝土量小)
    recommend = min(feas, key=lambda s: (s["steel_t"], s["concrete_m3"]))["name"] if feas else None
    return {"schemes": schemes, "feasible": feas,
            "pareto": [s["name"] for s in pareto], "recommend": recommend,
            "n_variants": len(variants), "n_feasible": len(feas)}


def render_markdown(rep: dict) -> str:
    L = ["# 生成式方案比选（设计书 §6.2 · 多目标 Pareto 前沿）\n",
         f"- 生成方案 **{rep['n_variants']}** 个（各为一 SSM 分支），可行 **{rep['n_feasible']}** 个",
         f"- Pareto 前沿：**{'、'.join(rep['pareto']) or '（无可行方案）'}**",
         f"- 推荐方案（满足全部规范且用钢量最小）：**{rep['recommend'] or '无——需放宽边界或调布置'}**", "",
         "| 方案 | 柱(mm) | 梁(mm) | 用钢量(t) | 混凝土(m³) | 层间位移角 | 周期比 | 规范 | Pareto |",
         "|---|---|---|---|---|---|---|---|---|"]
    front = set(rep["pareto"])
    for s in rep["schemes"]:
        ok = "✔ 满足" if s["feasible"] else f"✗ {s.get('reason','')}"
        drift = f"1/{int(1/s['drift_x'])}" if s.get("drift_x") else "-"
        pr = f"{s.get('period_ratio', 0):.2f}" if s["feasible"] else "-"
        st = f"{s['steel_t']:.2f}" if math.isfinite(s["steel_t"]) else "∞"
        star = "★" if s["name"] in front else ""
        L.append(f"| {s['name']}{'（推荐）' if s['name']==rep['recommend'] else ''} | "
                 f"{s['col'][0]}×{s['col'][1]} | {s['beam'][0]}×{s['beam'][1]} | "
                 f"{st} | {s['concrete_m3']} | {drift} | {pr} | {ok} | {star} |")
    L.append("\n*每个方案的规范判定来自确定性分析+规范引擎(玻璃盒可溯源)；比选只排序，最终选型由工程师拍板。*")
    return "\n".join(L)
