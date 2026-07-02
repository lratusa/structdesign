"""辖区解析器「必须 100% 正确」(设计书 §4.3 第一级)的可回归守护。

该步不用 AI、用规则表，因为它必须 100% 正确。本测试把"正确"变成断言：
- 确定性：同输入恒同输出(纯函数、无隐藏状态)。
- 覆盖矩阵：CN/EU/JP/US 建筑 + CN 水工，各自规范集匹配 §4.2 首发覆盖清单。
- 安全失败：未知辖区抛 ValueError(明确报错，绝不静默给错答案)。
- 引用完整：解析器 mandatory 里引用的每个强条 rule_id 都真实存在于规范引擎注册表(无悬空引用)。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.jurisdiction import resolve, list_jurisdictions, NDP
from heng.codes.registry import get


def test_determinism():
    for args in [("CN", "building"), ("CN", "gravity_dam"), ("EU", "building"),
                 ("JP", "building"), ("US", "building"), ("EU", "building", "design", "DE")]:
        a = resolve(*args); b = resolve(*args)
        assert a == b, f"辖区解析非确定性: {args}"


def test_coverage_matrix_matches_first_release_list():
    """对照 §4.2 首发规范覆盖清单逐辖区校验关键规范在位。"""
    cn = resolve("CN", "building")
    assert any("GB 50010" in c for c in cn.codes) and any("GB 50011" in c for c in cn.codes)
    assert any("GB 55001" in c for c in cn.codes) and any("GB 55002" in c for c in cn.codes)  # 通用强制

    cnw = resolve("CN", "gravity_dam")
    assert any("SL" in c or "NB" in c for c in cnw.codes), "CN 水工须返回 SL/NB 规范集"
    assert cnw is resolve("CN", "sluice"), "水闸/坝应同走水工规范集"

    eu = resolve("EU", "building")
    assert any("EN 1992-1-1" in c for c in eu.codes) and any("EN 1998" in c for c in eu.codes)
    assert eu.ndp, "EU 须带 NDP 参数层"

    jp = resolve("JP", "building")
    assert any("建築基準法" in c for c in jp.codes)

    us = resolve("US", "building")
    assert any("ASCE 7" in c for c in us.codes) and any("ACI 318" in c for c in us.codes)


def test_ndp_overlay_switches_by_national_annex():
    """同一 EC，切国别只换 NDP 参数集(不复制规则本体)。"""
    de = resolve("EU", "building", "design", "DE")
    assert de.ndp == NDP["DE"]
    rec = resolve("EU", "building")
    assert rec.ndp == NDP["EU-recommended"]


def test_unknown_jurisdiction_fails_safe():
    """未知辖区必须抛错，绝不静默返回错误规范集。"""
    try:
        resolve("XX", "building")
        assert False, "未知辖区应抛 ValueError"
    except ValueError:
        pass


def test_every_referenced_mandatory_rule_exists():
    """解析器 mandatory 里的每个 rule_id(形如 CN./EU./JP.…)都必须真实存在于注册表——无悬空强条引用。"""
    prefixes = ("CN.", "EU.", "JP.", "US.")
    combos = [("CN", "building"), ("CN", "gravity_dam"), ("EU", "building"),
              ("JP", "building"), ("US", "building")]
    dangling = []
    for c in combos:
        cs = resolve(*c)
        for m in cs.mandatory:
            if m.startswith(prefixes):          # 条文级 rule_id(非整册规范名)
                if get(m) is None:
                    dangling.append(m)
    assert not dangling, f"解析器引用了不存在的强条 rule_id(悬空引用): {dangling}"


def test_all_declared_jurisdictions_well_formed():
    for j in list_jurisdictions():
        cs = resolve(j, "building")
        assert cs.codes, f"{j} 规范集为空"
        assert cs.review_process, f"{j} 缺审查流程"


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
