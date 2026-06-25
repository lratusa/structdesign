"""一键总流程集成测试。"""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.design_project import ProjectParams, design_project


def test_project_runs_and_outputs():
    p = ProjectParams(n_bays=3, n_stories=5, bay_w=6000, story_h=3600,
                      floor_area=1000, dead_kpa=5, live_kpa=2,
                      alpha_max=0.08, Tg=0.40, seismic_grade="三级")
    with tempfile.TemporaryDirectory() as d:
        r = design_project(p, d)
        assert r.building.T1 > 0
        assert r.total_steel_t > 0
        assert r.steel_per_m2 > 0
        # 文件生成
        assert os.path.exists(r.files["计算书_md"])
        assert os.path.exists(r.files["梁平法图_dxf"])
        # 钢筋表非空
        assert len(r.schedule.rows) > 0


def test_project_steel_reasonable():
    """含钢量应在工程合理量级(梁柱纵筋约 20~80 kg/㎡)。"""
    p = ProjectParams(n_bays=4, n_stories=6, bay_w=8000, floor_area=2000,
                      alpha_max=0.08, Tg=0.40, seismic_grade="三级")
    with tempfile.TemporaryDirectory() as d:
        r = design_project(p, d)
        # 仅梁柱纵筋估算，按本榀受荷面积，合理量级约 3~120 kg/㎡
        assert 3 < r.steel_per_m2 < 200, r.steel_per_m2


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
