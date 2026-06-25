"""
真实框架模态分析验证。

刚性梁门式框架：两端固结柱+刚性梁，退化为 k=Σ12EI/h³, T=2π√(m/k)。
  E=30000, 柱 I=400⁴/12=2.133e9, h=3600 → k=2·12EI/h³
  k=24·30000·2.133e9/3600³=32922 N/mm=3.292e7 N/m; m=1e5kg
  ω=√(k/m)=18.14, T=2π/ω=0.3463 s
另：柔性梁应给出更长的 T1（梁柔度降低抗侧刚度）。
"""
import os
import sys
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame2d import FrameModel, Node, Member
from structdesign.analysis.frame_modal import frame_modal


def approx(a, b, tol=3e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def _portal(beam_I, mass=1e5):
    E = 30000.0
    Ic = 400 ** 4 / 12
    m = FrameModel()
    m.add_node(Node("1", 0, 0, (True, True, True)))
    m.add_node(Node("4", 6000, 0, (True, True, True)))
    m.add_node(Node("2", 0, 3600, (False, False, False)))
    m.add_node(Node("3", 6000, 3600, (False, False, False)))
    m.add_member(Member("c1", "1", "2", E, 1e5, Ic))
    m.add_member(Member("c2", "4", "3", E, 1e5, Ic))
    m.add_member(Member("b", "2", "3", E, 1e5, beam_I))
    return frame_modal(m, [mass])


def test_rigid_beam_portal_period():
    r = _portal(beam_I=1e13)   # 刚性梁
    E, Ic, h, mass = 30000.0, 400 ** 4 / 12, 3600.0, 1e5
    k = 2 * 12 * E * Ic / h ** 3 * 1000.0   # N/mm→N/m
    T = 2 * math.pi * math.sqrt(mass / k)
    assert approx(r.periods[0], T, 3e-2), (r.periods[0], T)


def test_flexible_beam_longer_period():
    rigid = _portal(beam_I=1e13).periods[0]
    flex = _portal(beam_I=2e8).periods[0]   # 柔性梁
    assert flex > rigid * 1.05, (flex, rigid)


def test_two_story_two_modes():
    E, Ic = 30000.0, 400 ** 4 / 12
    m = FrameModel()
    for nid, x, y, r in [("1", 0, 0, (True, True, True)), ("4", 6000, 0, (True, True, True)),
                          ("2", 0, 3600, (False,)*3), ("3", 6000, 3600, (False,)*3),
                          ("5", 0, 7200, (False,)*3), ("6", 6000, 7200, (False,)*3)]:
        m.add_node(Node(nid, x, y, r))
    for mid, a, b in [("c1", "1", "2"), ("c2", "4", "3"), ("c3", "2", "5"), ("c4", "3", "6")]:
        m.add_member(Member(mid, a, b, E, 1e5, Ic))
    for mid, a, b in [("b1", "2", "3"), ("b2", "5", "6")]:
        m.add_member(Member(mid, a, b, E, 1e5, 5e9))
    r = frame_modal(m, [1e5, 1e5])
    # 两层 → 两个侧移主模态，长周期在前
    assert r.periods[0] > r.periods[1] > 0
    assert r.n_master == 4  # 每层2节点ux


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
