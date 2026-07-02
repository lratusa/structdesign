"""辖区解析器(确定性) + NDP 参数覆盖 + 多国并行校核（设计书 §4.3/§4.4）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.jurisdiction import resolve, list_jurisdictions, NDP
from heng.codes.registry import get, check_all
from heng.codes.rule import check


def test_resolve_cn():
    cs = resolve("CN", "building", "design")
    assert cs.jurisdiction == "CN"
    assert any("GB 50010" in c for c in cs.codes)
    assert any("GB 55" in m for m in cs.mandatory)          # 通用规范强条
    assert "施工图审查" in cs.review_process


def test_resolve_unknown_raises():
    try:
        resolve("ZZ"); assert False
    except ValueError:
        pass


def test_eu_ndp_overlay():
    cs = resolve("EU", na="DE")
    assert cs.ndp.get("ndp_kc1") == 0.26 and cs.ndp.get("ndp_kc2") == 0.0013
    # NDP 注入上下文后 EC 规则可求值
    r = get("EU.EN1992-1-1.9.2.1.1")
    ctx = {"element": "beam", "material": "reinforced_concrete", "fctm": 2.9, "fyk": 500, "rho": 0.003}
    ctx.update(cs.ndp)
    res = check(r, ctx)
    assert res.applicable and res.ok is True
    assert abs(res.values["rho_min"] - 0.001508) < 1e-6


def test_parallel_dual_code_beam():
    """双规范并行(§4.4)：同一梁上下文，中国 8.5.1 与 Eurocode 9.2.1.1 各自独立校核。"""
    ctx = {"element": "beam", "material": "reinforced_concrete",
           "ft": 1.43, "fy": 360,           # 中国
           "fctm": 2.9, "fyk": 500,         # 欧洲
           "rho": 0.003}
    ctx.update(NDP["EU-recommended"])
    cn = check(get("CN.GB50010-2010(2015).8.5.1"), ctx)
    eu = check(get("EU.EN1992-1-1.9.2.1.1"), ctx)
    assert cn.applicable and eu.applicable
    # 两套规范各自算出各自的最小配筋率(用于解释差异，不互相换算)
    assert cn.values["rho_min"] == 0.002
    assert abs(eu.values["rho_min"] - 0.001508) < 1e-6
    assert cn.ok is True and eu.ok is True


def test_jurisdictions_listed():
    assert set(list_jurisdictions()) >= {"CN", "EU", "JP", "US"}


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
