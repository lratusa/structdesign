"""三维一键总流程集成测试。"""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.design_project_3d import design_project_3d


def test_runs_and_calcbook():
    with tempfile.TemporaryDirectory() as d:
        out = design_project_3d(2, 2, 5, 8000, 7000, 3600, d,
                                col_bh=(650, 650), wall_cols={(1, 1)}, wall_bh=(400, 3500),
                                alpha_max=0.08, Tg=0.40, seismic_grade="三级", n_modes=8)
        assert out.Tx > 0 and out.Tt > 0
        assert out.base_x > 0
        assert out.total_steel_t > 0
        assert out.n_members > 0
        assert os.path.exists(out.files["三维计算书_md"])
        assert os.path.exists(out.files["三维模型_svg"])
        # 计算书含三维指标
        txt = open(out.files["三维计算书_md"], encoding="utf-8").read()
        assert "周期比" in txt and "位移比" in txt and "双偏压" in txt


def test_period_ratio_and_disp_ratio_present():
    with tempfile.TemporaryDirectory() as d:
        out = design_project_3d(2, 2, 5, 8000, 7000, 3600, d,
                                col_bh=(650, 650), alpha_max=0.08, Tg=0.40, n_modes=8)
        assert "周期比 Tt/T1≤0.90" in out.checks
        assert out.disp_ratio_x >= 1.0


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
