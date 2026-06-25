"""多层多跨整榀框架闭环测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.frame_builder import build_regular_frame
from structdesign.frame_spec import SecBox
from structdesign.design_frame import closed_loop_design


def _factory_col():
    return SecBox(350, 350, "C40", "column", h_max=1000, seismic_grade="二级")


def _factory_beam():
    return SecBox(300, 550, "C30", "beam", h_max=1000, seismic_grade="二级")


def test_frame_topology():
    spec = build_regular_frame(3, 4, 6000, 3600, _factory_col, _factory_beam, 90.0, 80000.0)
    # 节点 (3+1)*(4+1)=20；构件 柱(3+1)*4 + 梁 3*4 = 16+12=28
    assert len(spec.nodes) == 20
    assert len(spec.members) == 28


def test_frame_converges_all_columns_ok():
    spec = build_regular_frame(3, 5, 6000, 3600, _factory_col, _factory_beam, 100.0, 90000.0)
    res = closed_loop_design(spec, h_step=50.0, max_iter=40)
    assert res.converged, res.history[-3:]
    cols = [k for k in res.final_forces if k.startswith("Z")]
    assert len(cols) == 20  # (3+1)列 × 5层
    over = [k for k in cols if "✗" in res.final_forces[k]]
    assert not over, over


def test_ground_columns_not_smaller_than_top():
    spec = build_regular_frame(2, 4, 6000, 3600, _factory_col, _factory_beam, 110.0, 80000.0)
    res = closed_loop_design(spec, h_step=50.0, max_iter=40)

    def h(sec_str):  # "350×500 C40" -> 500
        return float(sec_str.split("×")[1].split()[0])
    # 同一柱列，底层 h ≥ 顶层 h（轴力更大）
    ground = h(res.final_sections["Z1_1"])
    top = h(res.final_sections["Z1_4"])
    assert ground >= top, (ground, top)


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
