"""地震工况整榀配筋集成测试。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.frame_spec import SecBox
from structdesign.design_building import seismic_frame_design, seismic_closed_loop


def _col():
    return SecBox(650, 650, "C40", "column", h_max=1200, seismic_grade="三级")


def _beam():
    return SecBox(300, 700, "C30", "beam", h_max=1000, seismic_grade="三级")


def _run():
    return seismic_frame_design(
        n_bays=3, n_stories=6, bay_w=6000, story_h=3600,
        col_factory=_col, beam_factory=_beam, w_gravity=55.0,
        story_mass=3.0e5, alpha_max=0.08, Tg=0.40, seismic_grade="三级")


def test_runs_and_basic_outputs():
    bd = _run()
    assert bd.T1 > 0
    assert bd.base_shear > 0
    assert abs(bd.base_shear - max(bd.story_shears)) < 1e-6
    assert len(bd.members) == (3 + 1) * 6 + 3 * 6  # 柱24 + 梁18 = 42


def test_seismic_increases_demand():
    """含地震组合的设计弯矩应不小于仅重力弯矩(底层柱更明显)。"""
    bd = _run()
    cols = [m for k, m in bd.members.items() if m.kind == "column"]
    # 至少一根柱组合弯矩明显大于其重力弯矩
    assert any(m.M_combo > m.M_gravity * 1.2 + 1.0 for m in cols)


def test_capacity_design_amplifies_columns():
    """强柱弱梁：柱能力设计弯矩 ≥ 组合弯矩(二级 η=1.5)。"""
    bd = _run()
    for m in bd.members.values():
        if m.kind == "column":
            assert m.M_capacity >= m.M_combo - 1e-6


def test_all_members_reinforced():
    bd = _run()
    assert all(m.As > 0 for m in bd.members.values())


def test_shear_weight_ratio_reasonable():
    """剪重比应在工程合理区间(约2%~12%)，证明地震力量级正确(SRSS不被高估)。"""
    bd = _run()
    W = 6 * 3.0e5 * 9.81
    swr = bd.base_shear / W
    assert 0.02 <= swr <= 0.12, swr


def test_pdelta_amplifies():
    """P-Δ：含二阶的设计弯矩应≥不含(重力压力软化侧向刚度→放大)。"""
    def run(pd):
        return seismic_frame_design(3, 8, 6000, 3600,
            lambda: SecBox(500, 500, "C40", "column", h_max=1200, seismic_grade="二级"),
            lambda: SecBox(300, 650, "C30", "beam", h_max=1200, seismic_grade="二级"),
            70.0, 5.0e5, 0.16, 0.40, "二级", pdelta=pd)
    a, b = run(False), run(True)
    cols = [k for k in a.members if k.startswith("Z")]
    amp = [b.members[k].M_combo / max(a.members[k].M_combo, 1e-6) for k in cols]
    assert min(amp) >= 0.999, min(amp)        # 不会减小
    assert max(amp) > 1.01, max(amp)          # 确有放大


def test_undersized_section_flagged():
    """把梁/柱取得过小，应被标记 ok=False(截面不足/超限)，而非静默通过。"""
    def small_col():
        return SecBox(400, 400, "C40", "column", h_max=1200, seismic_grade="三级")
    def small_beam():
        return SecBox(250, 400, "C30", "beam", h_max=1000, seismic_grade="三级")
    bd = seismic_frame_design(3, 6, 6000, 3600, small_col, small_beam,
                              w_gravity=55.0, story_mass=3.0e5,
                              alpha_max=0.08, Tg=0.40, seismic_grade="三级")
    assert any(not m.ok for m in bd.members.values())


def _small_col():
    return SecBox(400, 400, "C40", "column", h_max=1200, seismic_grade="三级")


def _small_beam():
    return SecBox(250, 450, "C30", "beam", h_max=1000, seismic_grade="三级")


def test_seismic_loop_converges_all_ok():
    res = seismic_closed_loop(3, 6, 6000, 3600, _small_col, _small_beam,
                              55.0, 3.0e5, 0.08, 0.40, "三级", h_step=50.0)
    assert res.converged
    assert res.iterations >= 2
    assert all(m.ok for m in res.final.members.values())


def test_seismic_loop_modal_reruns():
    """各轮 T1 应随截面生长而变化(刚度变→周期变)，证明模态确实重算。"""
    import re
    res = seismic_closed_loop(3, 6, 6000, 3600, _small_col, _small_beam,
                              55.0, 3.0e5, 0.08, 0.40, "三级", h_step=50.0)
    T1s = [float(re.search(r"T1=([\d.]+)", h).group(1)) for h in res.history]
    assert max(T1s) - min(T1s) > 0.02, T1s     # T1 明显变化
    # 截面生长→刚度增→周期减
    assert T1s[0] >= T1s[-1] - 1e-9


def test_seismic_loop_grows_sections():
    """收敛后内柱底层截面应大于初始 400(发生过生长)。"""
    res = seismic_closed_loop(3, 6, 6000, 3600, _small_col, _small_beam,
                              55.0, 3.0e5, 0.08, 0.40, "三级", h_step=50.0)
    h = float(res.final_sections["Z1_1"].split("×")[1])
    assert h > 400


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
