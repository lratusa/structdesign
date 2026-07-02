"""强条漏检数=0 指标（产品设计书 §15 辅助北极星）的可度量守护。

手算校验(逐条违例落在判定错侧)：
  8.5.1  rho_min=max(0.002,0.45*1.43/360=0.00179)=0.002；rho=0.001 → 应判负
  5.5.1  框架 theta_lim=1/550=0.001818；drift=0.005 → 应判负
  5.2.5  8度 lam_min=0.032；shear_weight=0.010 → 应判负
  6.3.7  一级 rho_min=0.009；rho=0.005 → 应判负
  6.3.1  Vlim=0.25*1*14.3*300*660/1000=707.85kN；V=1000 → 应判负
  NBT35026 Ks=0.7*1e6/1e6=0.7；K_allow=3.0 → 应判负
  SL265抗浮 Kf=100/100=1.0；Kf_allow=1.1 → 应判负
  SL265抗滑 Kc=0.3*100/100=0.3；Kc_allow=1.25 → 应判负
  JP令77  rho=0.005 < 0.008 → 应判负
  JP令82の2 drift=0.010 > 0.005 → 应判负
  EN1992  rho_min=max(0.26*2.9/500=0.001508,0.0013)=0.001508；rho=0.0005 → 应判负
指标 = 漏检数(真漏检 + 未登记违例种子的强条)。目标恒为 0。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.redline import zero_miss_audit, VIOLATION_SEEDS, render_markdown
from heng.codes.registry import all_rules


def test_zero_miss():
    rep = zero_miss_audit()
    assert rep["miss_count"] == 0, f"强条漏检数 {rep['miss_count']} ≠ 0: {rep['misses']} / 未覆盖 {rep['uncovered']}"
    assert rep["zero_miss"] is True


def test_every_mandatory_rule_has_violation_seed():
    """全覆盖：每条强条必须登记违例种子(否则该强条从未被漏检测试触及)。"""
    mand = [r.rule_id for r in all_rules() if r.provenance.get("mandatory")]
    missing = [rid for rid in mand if rid not in VIOLATION_SEEDS]
    assert not missing, f"以下强条缺违例种子(潜在漏检): {missing}"


def test_specificity_no_blanket_alarm():
    """报警特异性：每条强条的合规算例必须通过——防止'永远报错'把漏检平凡刷成0。"""
    rep = zero_miss_audit()
    assert not rep["non_specific"], f"合规算例未通过(报警不特异): {rep['non_specific']}"


def test_each_seed_actually_flagged():
    """逐条断言：每个违例种子都被判为 applicable 且 verdict=False(真被标红线)。"""
    from heng.codes.registry import get
    from heng.codes.rule import check
    for rid, ctx in VIOLATION_SEEDS.items():
        r = get(rid)
        assert r is not None, f"注册表缺 {rid}"
        res = check(r, ctx)
        assert res.applicable, f"{rid} 违例种子 scope 未命中"
        assert res.ok is False, f"{rid} 违例种子未被判负(漏检!) values={res.values}"
        assert res.mandatory, f"{rid} 未标记为强条"


def test_render_markdown():
    md = render_markdown(zero_miss_audit())
    assert "强条漏检数" in md and "目标 = 0" in md
    assert "达标（零漏检）" in md


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
