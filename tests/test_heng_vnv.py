"""内核可信度基准库(设计书 §5.2)：自研 FEM/模态内核对经典闭合解全达标。

手算闭合解(用解析解验内核)：
  悬臂固定端弯矩 M=P·L=1e4·3000=3e7 N·mm
  简支梁跨中弯矩 M=wL²/8=20·6000²/8=9e7 N·mm
  两端固定梁端弯矩 M=wL²/12=20·6000²/12=6e7 N·mm
  悬臂固定端剪力 V=P=1e4 N（荷载守恒）
  单自由度周期 T=2π√(m/k)=2π√(1e5/1e7)=0.62832 s
  双层剪切型周期比 T1/T2=√((3+√5)/(3−√5))=2.61803
全部相对误差应 ≤ 1e-6（实测 ~1e-16 机器精度）。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng import vnv


def test_all_benchmarks_pass():
    rep = vnv.run_benchmarks()
    bad = [r["name"] for r in rep["rows"] if not r["pass"]]
    assert rep["all_pass"], f"超差基准: {bad}（最大相对误差 {rep['max_rel_error']:.2e}）"
    assert rep["n"] >= 6


def test_machine_precision():
    """闭合解基准应达机器精度(远严于 §5.2 的 2% 商业软件对比阈)。"""
    rep = vnv.run_benchmarks(tol=1e-9)
    assert rep["all_pass"], f"最大相对误差 {rep['max_rel_error']:.2e} 超 1e-9"


def test_each_uses_real_kernel_values():
    """逐题闭合解数值锚点(防内核悄悄回归)。"""
    rows = {r["name"]: r for r in vnv.run_benchmarks()["rows"]}
    approx = lambda a, b: abs(a - b) <= 1e-6 * abs(b)
    assert approx(rows["悬臂固定端弯矩"]["closed_form"], 3.0e7)
    assert approx(rows["简支梁跨中弯矩"]["closed_form"], 9.0e7)
    assert approx(rows["两端固定梁端弯矩"]["closed_form"], 6.0e7)
    assert approx(rows["单自由度自振周期"]["closed_form"], 0.6283185307)
    assert approx(rows["双层剪切型周期比"]["closed_form"], 2.6180339887)


def test_render_markdown():
    md = vnv.render_markdown(vnv.run_benchmarks())
    assert "内核可信度基准库" in md and "相对误差" in md
    assert "达标" in md


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
