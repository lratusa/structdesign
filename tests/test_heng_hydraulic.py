"""水工规范包(SL/NB)：重力坝抗滑/水闸抗浮抗滑稳定入引擎，多域(建筑+水工)统一（设计书 §7）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.registry import get, check_all, scan, rules_for
from heng.codes.rule import check, run_selftest
from heng.codes.jurisdiction import resolve


def test_water_rules_pass_ci():
    for rid in ("CN.NBT35026-2014.坝基抗滑稳定", "CN.SL265-2016.水闸抗浮", "CN.SL265-2016.水闸抗滑"):
        okk, msg = run_selftest(get(rid))
        assert okk, f"{rid}: {msg}"


def test_gravity_dam_sliding():
    r = get("CN.NBT35026-2014.坝基抗滑稳定")
    # 抗剪断: Ks=(f'ΣW+c'A)/ΣP=(1.0*50000+900*50)/18000=5.28≥3.0 → 满足
    res = check(r, {"element": "gravity_dam", "f_prime": 1.0, "c_prime": 900, "A": 50,
                    "sumW": 50000, "sumP": 18000, "K_allow": 3.0})
    assert res.applicable and res.ok is True and abs(res.values["Ks"] - 5.2778) < 1e-3
    assert res.mandatory                                   # 稳定是强条
    # 荷载增大→不满足
    bad = check(r, {"element": "gravity_dam", "f_prime": 1.0, "c_prime": 900, "A": 50,
                    "sumW": 50000, "sumP": 40000, "K_allow": 3.0})
    assert bad.ok is False


def test_sluice_antifloat_and_slide():
    af = check(get("CN.SL265-2016.水闸抗浮"),
               {"element": "sluice", "sumG": 12000, "sumU": 9000, "Kf_allow": 1.10})
    assert af.ok is True and abs(af.values["Kf"] - 1.3333) < 1e-3
    sl = check(get("CN.SL265-2016.水闸抗滑"),
               {"element": "sluice", "f": 0.5, "sumW": 20000, "sumP": 3000, "Kc_allow": 1.25})
    assert sl.ok is True


def test_jurisdiction_hydraulic_codeset():
    cs = resolve("CN", structure_type="gravity_dam")
    assert any("NB/T 35026" in c for c in cs.codes)         # 水工规范集
    assert "水利部" in cs.review_process
    # 建筑与水工规范集不同
    building = resolve("CN", structure_type="building")
    assert building.codes != cs.codes


def test_dam_scan_redline():
    # 抗滑不满足(强条)→红线；用 element=gravity_dam ctx 跑 CN 全部适用规则
    ctx = {"element": "gravity_dam", "f_prime": 0.6, "c_prime": 0, "A": 50,
           "sumW": 40000, "sumP": 40000, "K_allow": 3.0}
    res = [r for r in check_all(ctx, "CN") if r.applicable and r.ok is not None]
    assert any(not r.ok and r.mandatory for r in res)       # 坝抗滑强条不满足=红线


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
