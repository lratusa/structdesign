"""
剪力墙抗侧体系测试。

(1) 等效宽柱墙: 悬臂顶点位移 = PH³/3EI (解析)。
(2) 加墙后整体位移角显著减小、不足构件减少。
"""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame2d import FrameModel, Node, Member, NodalLoad
from structdesign.analysis.frame_modal import assemble_K
from structdesign.frame_spec import SecBox
from structdesign.design_building import seismic_frame_design


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_cantilever_wall_PH3_3EI():
    E, b, lw, H, P, n = 3e4, 300, 3000, 30000, 100000, 20
    I = b * lw ** 3 / 12
    m = FrameModel()
    for i in range(n + 1):
        r = (True, True, True) if i == 0 else (False, False, False)
        m.add_node(Node(str(i), 0, H * i / n, r))
    for i in range(n):
        m.add_member(Member(f"w{i}", str(i), str(i + 1), E, b * lw, I))
    K, idx, _ = assemble_K(m)
    ndof = 3 * len(m.nodes)
    F = np.zeros(ndof); F[3 * idx[str(n)]] = P
    fixed = set()
    for nid, nd in m.nodes.items():
        bb = 3 * idx[nid]
        for k, rr in enumerate(nd.restraint):
            if rr:
                fixed.add(bb + k)
    free = [d for d in range(ndof) if d not in fixed]
    U = np.zeros(ndof); U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    assert approx(U[3 * idx[str(n)]], P * H ** 3 / (3 * E * I), 1e-3)


def _common():
    return dict(n_bays=4, n_stories=10, bay_w=8000, story_h=3600,
                col_factory=lambda: SecBox(700, 700, "C40", "column", h_max=1200, seismic_grade="二级"),
                beam_factory=lambda: SecBox(350, 700, "C30", "beam", h_max=1200, seismic_grade="二级"),
                w_gravity=80.0, story_mass=1.0e6, alpha_max=0.16, Tg=0.45, seismic_grade="二级")


def test_wall_reduces_drift_and_inadequate():
    no_wall = seismic_frame_design(**_common())
    with_wall = seismic_frame_design(
        wall_axes=[2], wall_factory=lambda: SecBox(400, 8000, "C50", "wall", h_max=12000, seismic_grade="二级"),
        **_common())
    # 加墙后周期更短、位移角更小
    assert with_wall.T1 < no_wall.T1
    assert with_wall.drift_ratio < no_wall.drift_ratio
    nb0 = sum(0 if m.ok else 1 for m in no_wall.members.values())
    nb1 = sum(0 if m.ok else 1 for m in with_wall.members.values())
    assert nb1 <= nb0


def test_wall_member_designed():
    bd = seismic_frame_design(
        wall_axes=[2], wall_factory=lambda: SecBox(400, 6000, "C50", "wall", h_max=10000, seismic_grade="二级"),
        **_common())
    walls = [m for m in bd.members.values() if m.kind == "wall"]
    assert len(walls) == 10           # 10 层墙肢
    assert all("墙肢" in m.note for m in walls)


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
