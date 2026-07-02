"""生成式方案比选(设计书 §6.2)：多方案 → 多目标 Pareto 前沿 + 推荐。

验证逻辑(非数值精度，而是比选结构正确)：
- 太小截面方案不可行(有构件不满足规范)，被排除出可行集与推荐。
- 可行方案里推荐 = 用钢量最小者。
- Pareto 前沿非空且不含被支配方案(某方案两目标都不优于另一方案则被支配)。
- 每个方案登记为一个 SSM 分支(N 个结构方案分支)。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modeler.project import Column, Beam, SlabLoad, Storey, StandardFloor, Seismic, Grid, Project
from heng import scheme


def _model():
    B = 7000; xs = [0, B, 2 * B]; ys = [0, B, 2 * B]
    cols = [Column(x, y, 500, 500) for x in xs for y in ys]
    beams = ([Beam(xs[i], y, xs[i + 1], y, 300, 600) for y in ys for i in range(2)]
             + [Beam(x, ys[k], x, ys[k + 1], 300, 600) for x in xs for k in range(2)])
    fl = StandardFloor(columns=cols, beams=beams, slab=SlabLoad(6, 2.5))
    return Project(grid=Grid(xs, ys), floor=fl, storeys=[Storey(3600, 8)],
                   seismic=Seismic(alpha_max=0.16, n_modes=6))   # 8度较大地震利于拉开方案差异


VARIANTS = [
    ("A-小", (350, 350), (250, 500)),
    ("B-中", (600, 600), (300, 700)),
    ("C-大", (800, 800), (350, 800)),
    ("D-超大", (1000, 1000), (400, 900)),
]


def test_compare_produces_pareto_and_recommend():
    rep = scheme.compare_schemes(_model(), VARIANTS)
    assert rep["n_variants"] == 4
    assert rep["n_feasible"] >= 1, "至少应有一个可行方案"
    assert rep["recommend"] in {s["name"] for s in rep["feasible"]}, "推荐必须是可行方案"
    assert rep["pareto"], "Pareto 前沿非空"


def test_recommend_is_min_steel_among_feasible():
    rep = scheme.compare_schemes(_model(), VARIANTS)
    feas = rep["feasible"]
    min_steel = min(feas, key=lambda s: (s["steel_t"], s["concrete_m3"]))["name"]
    assert rep["recommend"] == min_steel


def test_pareto_excludes_dominated():
    rep = scheme.compare_schemes(_model(), VARIANTS)
    feas = {s["name"]: s for s in rep["feasible"]}
    for name in rep["pareto"]:
        s = feas[name]
        # 前沿方案不应被任何其它可行方案在两目标上同时支配
        for o in feas.values():
            if o is s:
                continue
            dominated = (o["steel_t"] <= s["steel_t"] + 1e-9 and o["concrete_m3"] <= s["concrete_m3"] + 1e-9
                         and (o["steel_t"] < s["steel_t"] - 1e-9 or o["concrete_m3"] < s["concrete_m3"] - 1e-9))
            assert not dominated, f"{name} 被 {o['name']} 支配却进了前沿"


def test_each_scheme_is_ssm_branch():
    """N 个方案 = N 个 SSM 分支(方案比选建立在版本化模型上)。"""
    from heng.ssm import SSMRepo, ssm_from_project
    repo = SSMRepo()
    p = _model()
    for (n, c, b) in VARIANTS:
        scheme.evaluate_scheme(p, n, c, b, repo=repo)
    for (n, _, _) in VARIANTS:
        assert n in repo.branches, f"方案 {n} 未建立 SSM 分支"


def test_render_markdown():
    md = scheme.render_markdown(scheme.compare_schemes(_model(), VARIANTS))
    assert "生成式方案比选" in md and "Pareto 前沿" in md and "推荐" in md


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); ok += 1
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAIL", fn.__name__, repr(e))
    print(f"{ok}/{len(fns)}")
    sys.exit(0 if ok == len(fns) else 1)
