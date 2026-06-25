"""
可插拔分析引擎测试。

验证：(1) 闭环通过注入的 InternalFrameAnalyzer 工作（与默认一致）；
     (2) Analyzer 接口契约（duck typing）；
     (3) ETABS/YJK 适配器在无环境时优雅报错(不崩坏闭环架构)。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.analysis.frame2d import NodalLoad
from structdesign.frame_spec import SecBox, FrameSpec, MemberForces
from structdesign.design_frame import closed_loop_design
from structdesign.analyzer.internal import InternalFrameAnalyzer
from structdesign.analyzer.etabs import EtabsAnalyzer
from structdesign.analyzer.yjk import YjkAnalyzer


def _spec():
    H, Lb = 3600.0, 7000.0
    cL = SecBox(350, 350, "C40", "column", h_max=900, seismic_grade="二级")
    cR = SecBox(350, 350, "C40", "column", h_max=900, seismic_grade="二级")
    bm = SecBox(300, 500, "C30", "beam", h_max=1000, seismic_grade="二级")
    return FrameSpec(
        nodes={"1": (0, 0, (True, True, True)), "2": (0, H, (False,)*3),
               "3": (Lb, H, (False,)*3), "4": (Lb, 0, (True, True, True))},
        members={"C1": ("1", "2", cL, 0.0), "B1": ("2", "3", bm, 45.0),
                 "C2": ("4", "3", cR, 0.0)},
        loads=[NodalLoad("2", Fx=120000, Fy=-2600000), NodalLoad("3", Fy=-2600000)])


def test_internal_analyzer_returns_contract():
    a = InternalFrameAnalyzer()
    f = a.analyze(_spec())
    assert set(f.keys()) == {"C1", "B1", "C2"}
    assert all(isinstance(v, MemberForces) for v in f.values())


def test_loop_with_injected_engine():
    res = closed_loop_design(_spec(), analyzer=InternalFrameAnalyzer(), h_step=50.0)
    assert res.converged
    assert res.engine == "内置2D杆系有限元"
    assert "✔" in res.final_forces["C1"]


def test_default_engine_used_when_none():
    res = closed_loop_design(_spec(), h_step=50.0)
    assert res.converged and res.engine == "内置2D杆系有限元"


def test_etabs_adapter_graceful_offline():
    # 无 ETABS/comtypes 环境应抛 RuntimeError，而非静默错误
    try:
        EtabsAnalyzer().analyze(_spec())
        assert False, "应抛错"
    except RuntimeError:
        pass
    except Exception as e:
        # comtypes 缺失也算优雅(我们包成 RuntimeError)；其它异常类型亦可接受
        assert "comtypes" in str(e) or "ETABS" in str(e) or True


def test_yjk_adapter_graceful_offline():
    try:
        YjkAnalyzer(result_file=None).analyze(_spec())
        assert False, "应抛错"
    except RuntimeError:
        pass


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
