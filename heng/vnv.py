"""内核可信度基准库 V&V（产品设计书 §5.2）——对**自研 FEM/模态内核**跑经典闭合解基准。

"替换的前提是信任。"平台维护公开对标基准库：解析解/守恒律标准题(NAFEMS 风格)，每次内核发版
全量重跑并公开逐题相对误差；差异 > 容差者须逐项解释。本库也是迁移工具(§9)的验收标准之一。

每题直接调用真实内核(`structdesign.analysis.frame2d.solve` / `modal.solve_shear_building`)，
与手写闭合解比对——**不是重算一遍公式**，而是用公式验内核。
"""
from __future__ import annotations
import math
from structdesign.analysis import frame2d as f2
from structdesign.analysis import modal

_E = 3.0e4        # N/mm² (C30)
_I = 300 * 600 ** 3 / 12.0     # mm⁴
_A = 300 * 600.0               # mm²


def _rel(got, exact):
    return abs(got - exact) / (abs(exact) if abs(exact) > 1e-12 else 1.0)


def _cantilever_fixed_moment():
    """悬臂端受集中力 P：固定端弯矩 M = P·L。"""
    L, P = 3000.0, 1.0e4
    m = f2.FrameModel()
    m.add_node(f2.Node("A", 0, 0, (True, True, True)))
    m.add_node(f2.Node("B", L, 0, (False, False, False)))
    m.add_member(f2.Member("AB", "A", "B", _E, _A, _I))
    m.add_load(f2.NodalLoad("B", Fy=-P))
    r = f2.solve(m)["AB"]
    return abs(r.Mi), P * L, "M=P·L（悬臂固定端弯矩）"


def _ss_beam_midspan_moment():
    """简支梁均布 w：跨中弯矩 M = wL²/8。"""
    L, w = 6000.0, 20.0
    m = f2.FrameModel()
    m.add_node(f2.Node("A", 0, 0, (True, True, False)))    # 铰
    m.add_node(f2.Node("B", L, 0, (False, True, False)))   # 滚
    m.add_member(f2.Member("AB", "A", "B", _E, _A, _I, w=w))
    r = f2.solve(m)["AB"]
    return abs(r.M_mid), w * L ** 2 / 8.0, "M=wL²/8（简支梁跨中弯矩）"


def _fixed_fixed_end_moment():
    """两端固定梁均布 w：端弯矩 M = wL²/12。"""
    L, w = 6000.0, 20.0
    m = f2.FrameModel()
    m.add_node(f2.Node("A", 0, 0, (True, True, True)))
    m.add_node(f2.Node("B", L, 0, (True, True, True)))
    m.add_member(f2.Member("AB", "A", "B", _E, _A, _I, w=w))
    r = f2.solve(m)["AB"]
    return abs(r.Mi), w * L ** 2 / 12.0, "M=wL²/12（两端固定梁端弯矩）"


def _cantilever_tip_shear():
    """悬臂端集中力：固定端剪力 V = P（竖向平衡/荷载守恒）。"""
    L, P = 3000.0, 1.0e4
    m = f2.FrameModel()
    m.add_node(f2.Node("A", 0, 0, (True, True, True)))
    m.add_node(f2.Node("B", L, 0, (False, False, False)))
    m.add_member(f2.Member("AB", "A", "B", _E, _A, _I))
    m.add_load(f2.NodalLoad("B", Fy=-P))
    r = f2.solve(m)["AB"]
    return abs(r.Vi), P, "V=P（悬臂固定端剪力=荷载守恒）"


def _sdof_period():
    """单自由度周期 T = 2π√(m/k)。"""
    mass, k = 1.0e5, 1.0e7
    T = modal.solve_shear_building([mass], [k]).periods[0]
    return T, 2 * math.pi * math.sqrt(mass / k), "T=2π√(m/k)（单自由度自振周期）"


def _two_dof_period_ratio():
    """等质量等刚度双层剪切型：ω²=(3∓√5)/2·(k/m)，故 T1/T2=√((3+√5)/(3−√5))。"""
    mass, k = 1.0e5, 1.0e7
    P = modal.solve_shear_building([mass, mass], [k, k]).periods
    got = P[0] / P[1]
    exact = math.sqrt((3 + math.sqrt(5)) / (3 - math.sqrt(5)))
    return got, exact, "T1/T2=√((3+√5)/(3−√5))（双层剪切型周期比，(3±√5)/2 特征值）"


_BENCHMARKS = [
    ("悬臂固定端弯矩", "GB 结构力学·悬臂梁", _cantilever_fixed_moment),
    ("简支梁跨中弯矩", "GB 结构力学·简支梁", _ss_beam_midspan_moment),
    ("两端固定梁端弯矩", "GB 结构力学·固端梁", _fixed_fixed_end_moment),
    ("悬臂固定端剪力(荷载守恒)", "静力平衡", _cantilever_tip_shear),
    ("单自由度自振周期", "结构动力学·SDOF", _sdof_period),
    ("双层剪切型周期比", "结构动力学·(3±√5)/2", _two_dof_period_ratio),
]


def run_benchmarks(tol: float = 1e-6) -> dict:
    """全量重跑基准，返回逐题相对误差 + 是否在容差内。"""
    rows = []
    for name, source, fn in _BENCHMARKS:
        got, exact, theory = fn()
        rel = _rel(got, exact)
        rows.append({"name": name, "source": source, "theory": theory,
                     "computed": got, "closed_form": exact,
                     "rel_error": rel, "tol": tol, "pass": rel <= tol})
    n_pass = sum(1 for r in rows if r["pass"])
    return {"rows": rows, "n": len(rows), "n_pass": n_pass,
            "max_rel_error": max(r["rel_error"] for r in rows),
            "all_pass": n_pass == len(rows), "tol": tol}


def render_markdown(rep: dict) -> str:
    L = ["# 内核可信度基准库 V&V（设计书 §5.2 · 每次发版全量重跑）\n",
         f"- 基准题 **{rep['n']}** 道，通过 **{rep['n_pass']}**，"
         f"最大相对误差 **{rep['max_rel_error']:.2e}**（容差 {rep['tol']:.0e}）",
         f"- {'✔ **内核对全部闭合解基准达标**' if rep['all_pass'] else '✗ 存在超差项(须逐项解释)'}", "",
         "| 基准 | 理论闭合解 | 依据 | 内核值 | 闭合解 | 相对误差 | 判定 |",
         "|---|---|---|---|---|---|---|"]
    for r in rep["rows"]:
        v = "✔" if r["pass"] else "✗ 超差"
        L.append(f"| {r['name']} | {r['theory']} | {r['source']} | "
                 f"{r['computed']:.6g} | {r['closed_form']:.6g} | {r['rel_error']:.2e} | {v} |")
    L.append("\n*本基准库对自研 FEM/模态内核跑经典闭合解——用解析解验内核，非重算公式；"
             "商业软件(PKPM/YJK/ETABS)同模型对比需正版环境，属现场对标环节。*")
    return "\n".join(L)
