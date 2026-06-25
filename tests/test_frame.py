"""
2D 杆系有限元验证 —— 经典解析解核对。

简支梁 UDL: M_mid=wL²/8, 端弯矩=0
固支梁 UDL: 端弯矩=wL²/12, 中=wL²/24
柱轴力: 竖向荷载 P → 轴力=P
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame2d import FrameModel, Node, Member, NodalLoad, solve


def approx(a, b, tol=1e-4):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_simply_supported_udl():
    m = FrameModel()
    m.add_node(Node("1", 0, 0, (True, True, False)))
    m.add_node(Node("2", 6000, 0, (False, True, False)))
    m.add_member(Member("b", "1", "2", 2e4, 1e5, 1e9, w=10))
    r = solve(m)["b"]
    assert approx(r.M_mid, 10 * 6000**2 / 8), r.M_mid
    assert approx(r.Mi, 0, 1e-6) and approx(r.Mj, 0, 1e-6)


def test_fixed_fixed_udl():
    m = FrameModel()
    m.add_node(Node("1", 0, 0, (True, True, True)))
    m.add_node(Node("2", 6000, 0, (True, True, True)))
    m.add_member(Member("b", "1", "2", 2e4, 1e5, 1e9, w=10))
    r = solve(m)["b"]
    assert approx(abs(r.Mi), 10 * 6000**2 / 12), r.Mi
    assert approx(r.M_mid, 10 * 6000**2 / 24), r.M_mid


def test_column_axial():
    m = FrameModel()
    m.add_node(Node("1", 0, 0, (True, True, True)))
    m.add_node(Node("2", 0, 3000, (False, False, False)))
    m.add_member(Member("c", "1", "2", 2e4, 1e5, 1e9))
    m.add_load(NodalLoad("2", Fy=-100000))  # 100 kN 向下
    r = solve(m)["c"]
    assert approx(r.N_axial, 100000), r.N_axial  # 压为正


def test_stiffness_changes_forces():
    """不等跨连续梁：第二跨刚度变化 → 内力重分布 → 第一跨跨中弯矩改变。

    （注：等跨等载时中支座弯矩与刚度无关而抵消，故须用不等跨验证重分布。）
    """
    def midspan(I2):
        m = FrameModel()
        m.add_node(Node("1", 0, 0, (True, True, False)))
        m.add_node(Node("2", 6000, 0, (False, True, False)))
        m.add_node(Node("3", 10000, 0, (False, True, False)))  # 不等跨
        m.add_member(Member("b1", "1", "2", 2e4, 1e5, 1e9, w=10))
        m.add_member(Member("b2", "2", "3", 2e4, 1e5, I2, w=10))
        return solve(m)["b1"].M_mid
    a = midspan(1e9)
    b = midspan(8e9)
    assert abs(a - b) > 1e4, (a, b)


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
