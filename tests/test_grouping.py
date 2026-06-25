"""钢筋归并测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.detailing.grouping import group_rebar


def test_each_member_satisfied():
    req = {"L1": 1000, "L2": 1050, "L3": 1100, "L4": 1500, "L5": 1520}
    ga = group_rebar(req, b=300)
    for m, As in req.items():
        assert ga.member_to_As[m] >= As


def test_merge_reduces_kinds():
    req = {"L1": 1000, "L2": 1050, "L3": 1100, "L4": 1500, "L5": 1520}
    full = group_rebar(req, b=300)              # 不限
    merged = group_rebar(req, b=300, max_kinds=2)
    assert len(merged.kinds) <= 2
    assert len(merged.kinds) <= len(full.kinds)
    # 归并后仍满足各自需求
    for m, As in req.items():
        assert merged.member_to_As[m] >= As
    # 归并通常增加用钢(升配)，浪费率不应小于未归并
    assert merged.waste_ratio >= full.waste_ratio - 1e-9


def test_single_kind():
    req = {"A": 800, "B": 1600}
    ga = group_rebar(req, b=300, max_kinds=1)
    assert len(ga.kinds) == 1
    assert ga.member_to_As["A"] >= 1600  # 都升到能覆盖最大需求


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
