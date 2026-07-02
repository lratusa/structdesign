"""规范 DSL —— 求值正确性 + 受限性(非图灵完备)安全校验。

手算基准：max(0.002, 0.45*1.43/360)=0.002；interp(8,[6,7,8,9],[0.04,0.08,0.16,0.32])=0.16；
lookup('二级',['一级','二级'],[0.65,0.75])=0.75；三元与比较逐一验证。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.codes.dsl import evaluate, evaluate_block, DSLError


def test_arithmetic_and_funcs():
    assert abs(evaluate("0.45*ft/fy", {"ft": 1.43, "fy": 360}) - 0.001788) < 1e-6
    assert evaluate("max(0.002, 0.45*ft/fy)", {"ft": 1.43, "fy": 360}) == 0.002
    assert evaluate("sqrt(a*a+b*b)", {"a": 3, "b": 4}) == 5.0
    assert evaluate("ceil(x)", {"x": 2.1}) == 3


def test_compare_bool_ternary():
    assert evaluate("rho >= rho_min", {"rho": 0.003, "rho_min": 0.002}) is True
    assert evaluate("rho >= rho_min", {"rho": 0.001, "rho_min": 0.002}) is False
    assert evaluate("mu <= lim and rho > 0", {"mu": 0.7, "lim": 0.75, "rho": 0.003}) is True
    v = evaluate("0.65 if g=='一级' else 0.75 if g=='二级' else 0.85", {"g": "二级"})
    assert v == 0.75


def test_interp_lookup():
    assert evaluate("interp(8, [6,7,8,9], [0.04,0.08,0.16,0.32])", {}) == 0.16
    assert evaluate("interp(7.5, [7,8], [0.08,0.16])", {}) == 0.12
    assert evaluate("lookup(g, ['一级','二级'], [0.65,0.75])", {"g": "二级"}) == 0.75


def test_assign_block():
    env = evaluate_block(["rho_min = max(0.002, 0.45*ft/fy)", "ok = rho >= rho_min"],
                         {"ft": 1.43, "fy": 360, "rho": 0.003})
    assert env["rho_min"] == 0.002 and env["ok"] is True


def test_rejects_unsafe():
    for bad in ["__import__('os')", "(1).__class__", "a.b", "[x for x in [1]]",
                "lambda: 1", "open('x')", "print(1)", "{k: 1}"]:
        try:
            evaluate(bad, {"a": 1})
            assert False, f"应拒绝: {bad}"
        except DSLError:
            pass


def test_undefined_var_errors():
    try:
        evaluate("nope + 1", {})
        assert False
    except DSLError:
        pass


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
