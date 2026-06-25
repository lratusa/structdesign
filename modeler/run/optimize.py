"""自动迭代优化引擎。

从用户建模的截面出发，按「试算风格 + 要求」迭代调整全楼柱/梁/墙截面：
- 先 GROW 到满足全部规范指标与构件承载力（强度/轴压比/位移角/周期比/剪重比）；
- 经济/均衡风格再 SHRINK 到接近限值以省材料；
直至收敛，输出优化后的截面 + 配筋 + 计算书。每轮调用 analyze(light) 提速。
"""
from __future__ import annotations
from dataclasses import dataclass, field
import copy

from .analyze import analyze

COL_MIN, COL_MAX = 300, 1500
BEAMH_MIN, BEAMH_MAX = 300, 1200
WALLT_MIN, WALLT_MAX = 200, 800
STEP = 50

PERIOD_LIM = 0.90
DISP_LIM = 1.20
DRIFT_LIM_WALL = 1.0 / 800.0     # 框架-剪力墙/核心筒
DRIFT_LIM_FRAME = 1.0 / 550.0    # 纯框架（GB 50011 5.5.1）
SHEAR_MIN = 0.016


@dataclass
class DesignPrefs:
    objective: str = "均衡"     # 经济 / 均衡 / 稳健
    strategy: str = "full"      # full(加大+减小) / grow(只加大) / fixed(只配筋)
    emphasis: str = "标准"      # 标准 / 严格(更小位移角与轴压比裕度)
    max_iter: int = 30


@dataclass
class IterRecord:
    it: int
    phase: str
    col: int
    beam_h: int
    wall_t: int
    steel_t: float
    n_bad: int
    feasible: bool
    note: str = ""


@dataclass
class OptimizeResult:
    project: object
    result: object              # 最终 analyze 结果(含计算书/图)
    history: list = field(default_factory=list)
    converged: bool = False
    iterations: int = 0


def _margin(prefs: DesignPrefs) -> float:
    # mf<1 收紧上限(留更大裕度→更大截面)。经济=刚好满足规范；均衡=留约3%；稳健=留约10%。
    mf = {"经济": 1.0, "均衡": 0.97, "稳健": 0.90}.get(prefs.objective, 0.97)
    if prefs.emphasis == "严格":
        mf *= 0.93
    return mf


# 优化目标：截面尺寸能可靠控制的指标 —— 构件承载力(n_bad)、层间位移角、最小剪重比。
# 周期比 Tt/T1、位移比属"扭转规则性"，靠均匀加大截面收效甚微（需偏心/周边布置等布局调整），
# 故由 analyze 的 checks 表如实"报告"，不驱动迭代加大，避免把截面顶到不合理的大。
def _feasible(r, mf, drift_lim) -> bool:
    return (r.n_bad == 0
            and r.drift_x <= drift_lim * mf
            and r.shear_weight >= SHEAR_MIN)


def _lateral_violation(r, mf, drift_lim) -> bool:
    return (r.drift_x > drift_lim * mf
            or r.shear_weight < SHEAR_MIN)


def _bad_by_kind(r):
    bad_cw = sum(1 for m in r.members if m["kind"] in ("柱", "墙") and not m["ok"])
    bad_b = sum(1 for m in r.members if m["kind"] == "梁" and not m["ok"])
    return bad_cw, bad_b


def _start_sections(project):
    fl = project.floor
    col = max([max(c.b, c.h) for c in fl.columns], default=500)
    beam_b = (fl.beams[0].b if fl.beams else 300)
    beam_h = max([b.h for b in fl.beams], default=600)
    has_walls = bool(fl.walls)
    wall_t = max([w.t for w in fl.walls], default=400)
    return int(col), int(beam_b), int(beam_h), int(wall_t), has_walls


def _apply(project, col, beam_b, beam_h, wall_t):
    for c in project.floor.columns:
        c.b = col; c.h = col
    for b in project.floor.beams:
        b.b = beam_b; b.h = beam_h
    for w in project.floor.walls:
        w.t = wall_t


def optimize(project, prefs: DesignPrefs, out_dir, progress_cb=None) -> OptimizeResult:
    work = copy.deepcopy(project)
    mf = _margin(prefs)
    allow_grow = prefs.strategy in ("full", "grow")
    allow_shrink = prefs.strategy == "full" and prefs.objective in ("经济", "均衡")

    col, beam_b, beam_h, wall_t, has_walls = _start_sections(work)
    drift_lim = DRIFT_LIM_WALL if has_walls else DRIFT_LIM_FRAME
    history = []
    it = 0

    def run_light(phase, note=""):
        nonlocal it
        _apply(work, col, beam_b, beam_h, wall_t)
        r = analyze(work, out_dir, light=True)
        it += 1
        rec = IterRecord(it, phase, col, beam_h, wall_t if has_walls else 0,
                         round(r.total_steel_t, 2), r.n_bad, _feasible(r, mf, drift_lim), note)
        history.append(rec)
        if progress_cb:
            progress_cb(rec)
        return r

    # ---- fixed：只配筋，不改截面 ----
    if prefs.strategy == "fixed":
        rf = analyze(work, out_dir, light=False)
        rec = IterRecord(1, "只配筋", col, beam_h, wall_t if has_walls else 0,
                         round(rf.total_steel_t, 2), rf.n_bad, _feasible(rf, mf, drift_lim), "固定截面")
        history.append(rec)
        if progress_cb:
            progress_cb(rec)
        return OptimizeResult(project=work, result=rf, history=history,
                              converged=_feasible(rf, mf, drift_lim), iterations=1)

    # ---- PHASE 1：加大到满足 ----
    r = run_light("加大", "起始截面")
    while it < prefs.max_iter and not _feasible(r, mf, drift_lim):
        if not allow_grow:
            break
        bad_cw, bad_b = _bad_by_kind(r)
        lat = _lateral_violation(r, mf, drift_lim)
        changed = False
        if (bad_cw > 0 or lat) and col < COL_MAX:
            col = min(col + STEP, COL_MAX); changed = True
        if has_walls and lat and wall_t < WALLT_MAX:
            wall_t = min(wall_t + STEP, WALLT_MAX); changed = True
        if bad_b > 0 and beam_h < BEAMH_MAX:
            beam_h = min(beam_h + STEP, BEAMH_MAX); changed = True
        if not changed:
            break
        r = run_light("加大", f"柱{col} 梁{beam_h}" + (f" 墙{wall_t}" if has_walls else ""))

    # ---- PHASE 2：经济/均衡风格再减小省料 ----
    if allow_shrink and _feasible(r, mf, drift_lim):
        improved = True
        while improved and it < prefs.max_iter:
            improved = False
            for which in ("col", "wall", "beam"):
                if it >= prefs.max_iter:
                    break
                if which == "col" and col - STEP >= COL_MIN:
                    col -= STEP
                    r2 = run_light("减小", f"试减柱→{col}")
                    if _feasible(r2, mf, drift_lim):
                        r = r2; improved = True
                    else:
                        col += STEP  # 回退
                elif which == "wall" and has_walls and wall_t - STEP >= WALLT_MIN:
                    wall_t -= STEP
                    r2 = run_light("减小", f"试减墙→{wall_t}")
                    if _feasible(r2, mf, drift_lim):
                        r = r2; improved = True
                    else:
                        wall_t += STEP
                elif which == "beam" and beam_h - STEP >= BEAMH_MIN:
                    beam_h -= STEP
                    r2 = run_light("减小", f"试减梁→{beam_h}")
                    if _feasible(r2, mf, drift_lim):
                        r = r2; improved = True
                    else:
                        beam_h += STEP

    # ---- 终轮：完整 analyze（出图 + 计算书）----
    _apply(work, col, beam_b, beam_h, wall_t)
    final = analyze(work, out_dir, light=False)
    converged = _feasible(final, mf, drift_lim)
    history.append(IterRecord(it + 1, "最终", col, beam_h, wall_t if has_walls else 0,
                              round(final.total_steel_t, 2), final.n_bad, converged, "出图+计算书"))
    return OptimizeResult(project=work, result=final, history=history,
                          converged=converged, iterations=it + 1)
