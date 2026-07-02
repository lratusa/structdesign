"""强条漏检数审计 —— 产品设计书 §15 辅助北极星指标「强条漏检数(目标为零)」的可度量实现。

北极星「一次送审通过率」是市场结果，不可一次编码达成；但其**辅助指标「强条漏检数=0」**
是可在代码里度量并守护的工程指标。本模块把它做成平台能力：

  对引擎覆盖的**每一条强制性条文**，注入一个已知违例上下文（VIOLATION_SEEDS），
  断言引擎必须把它标为红线（零假阴性 / 零漏检）；再用每条规则自带的合规算例(run_selftest)
  验证引擎不会无差别报警（specificity——否则"永远报错"会平凡地把漏检刷成 0 却毫无意义）；
  并强制**每条强条都有违例种子**（未覆盖的强条按保守口径计入漏检，逼迫补齐）。

漏检数 = 已知违例中未被标出的条数 + 无违例种子的强条条数。目标恒为 0，`test_heng_redline` 守护。
"""
from __future__ import annotations
from .codes.registry import all_rules
from .codes.rule import check, run_selftest
from .codes.jurisdiction import resolve

# —— 每条强条的「已知违例」种子：仅违反该条、scope 命中，违例值经手算落在判定错侧 ——
# 手算见各行注释；新增强条必须在此登记违例种子，否则审计判定其为「未覆盖漏检」而失败。
_EU_NDP = resolve("EU").ndp   # EN1992 NDP 参数层(kc1/kc2)

VIOLATION_SEEDS = {
    # 梁最小配筋率: rho_min=max(0.002,0.45*1.43/360=0.00179)=0.002；违例 rho=0.001<0.002
    "CN.GB50010-2010(2015).8.5.1":
        {"element": "beam", "material": "reinforced_concrete", "ft": 1.43, "fy": 360, "rho": 0.001},
    # 层间位移角(框架): theta_lim=1/550=0.00182；违例 drift=0.005
    "CN.GB50011-2010(2016).5.5.1":
        {"element": "story", "system": "frame", "drift": 0.005},
    # 剪重比(8度): lam_min=0.032；违例 shear_weight=0.010
    "CN.GB50011-2010(2016).5.2.5":
        {"element": "structure", "intensity": "8", "shear_weight": 0.010},
    # 柱最小配筋率(一级): rho_min=0.009；违例 rho=0.005
    "CN.GB50011-2010(2016).6.3.7":
        {"element": "column", "material": "reinforced_concrete", "grade": "一级", "rho": 0.005},
    # 梁剪压比: Vlim=0.25*1*14.3*300*660/1000=707.9kN；违例 V=1000kN
    "CN.GB50010-2010(2015).6.3.1":
        {"element": "beam", "material": "reinforced_concrete",
         "betac": 1.0, "fc": 14.3, "b": 300, "h0": 660, "V": 1000},
    # 重力坝坝基抗滑: Ks=(0.7*1e6+0)/1e6=0.7；违例 K_allow=3.0
    "CN.NBT35026-2014.坝基抗滑稳定":
        {"element": "gravity_dam", "f_prime": 0.7, "c_prime": 0.0,
         "sumW": 1.0e6, "A": 1.0, "sumP": 1.0e6, "K_allow": 3.0},
    # 水闸抗浮: Kf=100/100=1.0；违例 Kf_allow=1.1
    "CN.SL265-2016.水闸抗浮":
        {"element": "sluice", "sumG": 100.0, "sumU": 100.0, "Kf_allow": 1.1},
    # 水闸抗滑: Kc=0.3*100/100=0.3；违例 Kc_allow=1.25
    "CN.SL265-2016.水闸抗滑":
        {"element": "sluice", "f": 0.3, "sumW": 100.0, "sumP": 100.0, "Kc_allow": 1.25},
    # 日本 柱主筋≥0.8%: 违例 rho=0.005
    "JP.建築基準法施行令.77":
        {"element": "column", "material": "reinforced_concrete", "rho": 0.005},
    # 日本 层间变形角≤1/200=0.005: 违例 drift=0.010
    "JP.建築基準法施行令.82の2":
        {"element": "story", "drift": 0.010},
    # Eurocode 梁最小配筋: rho_min=max(0.26*2.9/500=0.00151,0.0013)=0.00151；违例 rho=0.0005
    "EU.EN1992-1-1.9.2.1.1":
        dict({"element": "beam", "material": "reinforced_concrete",
              "fctm": 2.9, "fyk": 500.0, "rho": 0.0005}, **_EU_NDP),
}


def zero_miss_audit() -> dict:
    """审计引擎对全部强条的漏检情况。返回可报告的指标字典。

    miss_count == 0 当且仅当：① 每条强条都有违例种子(全覆盖)；② 每个违例都被标为红线(零假阴性)；
    ③ 每条强条的合规算例都通过(specificity，非无差别报警)。
    """
    mand = [r for r in all_rules() if r.provenance.get("mandatory")]
    covered, uncovered, misses, non_specific = [], [], [], []
    for r in mand:
        seed = VIOLATION_SEEDS.get(r.rule_id)
        if seed is None:
            uncovered.append(r.rule_id)          # 未登记违例 → 保守计为潜在漏检
            continue
        res = check(r, seed)
        flagged = res.applicable and res.ok is False
        if flagged:
            covered.append(r.rule_id)
        else:
            misses.append({"rule_id": r.rule_id,
                           "applicable": res.applicable, "verdict": res.ok,
                           "reason": "scope未命中" if not res.applicable else "违例未被判负"})
        # specificity：合规算例必须通过(否则"永远报错"会把漏检平凡刷成0)
        st_ok, st_msg = run_selftest(r)
        if not st_ok:
            non_specific.append({"rule_id": r.rule_id, "selftest": st_msg})
    miss_count = len(misses) + len(uncovered)
    return {
        "indicator": "强条漏检数",
        "target": 0,
        "miss_count": miss_count,
        "mandatory_total": len(mand),
        "covered": covered,
        "uncovered": uncovered,          # 无违例种子的强条(须补齐)
        "misses": misses,                # 有种子但未被标出(真漏检)
        "non_specific": non_specific,    # 合规算例未通过(报警不特异)
        "zero_miss": miss_count == 0 and not non_specific,
    }


def render_markdown(rep: dict) -> str:
    L = [f"# 强条漏检数审计（北极星辅助指标 · 目标 = {rep['target']}）\n",
         f"- 引擎覆盖强制性条文：**{rep['mandatory_total']}** 条",
         f"- 已注入违例并被正确标红线：**{len(rep['covered'])}** 条",
         f"- **强条漏检数 = {rep['miss_count']}**"
         + ("　✔ **达标（零漏检）**" if rep["zero_miss"] else "　✗ **未达标**"), ""]
    if rep["uncovered"]:
        L.append("## 未登记违例种子的强条（保守计入漏检，须补齐）")
        L += [f"- `{x}`" for x in rep["uncovered"]] + [""]
    if rep["misses"]:
        L.append("## 真漏检（违例未被标出）")
        L += [f"- `{m['rule_id']}`：{m['reason']}" for m in rep["misses"]] + [""]
    if rep["non_specific"]:
        L.append("## 报警不特异（合规算例未通过）")
        L += [f"- `{m['rule_id']}`" for m in rep["non_specific"]] + [""]
    L.append("*本审计把设计书 §15 辅助指标「强条漏检数=0」做成可回归的工程度量；"
             "每条强条同时带合规算例与违例算例，任一新增强条须两者齐备方能入库。*")
    return "\n".join(L)
