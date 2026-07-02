"""模型迁移器 + 迁移诊断报告（设计书 §9）：透明映射、有损标注、需人工补充、可进版本库。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.migrate import import_model, render_report
from heng.ssm import SSMRepo


def _external():
    return {"members": [
        {"id": "C1", "type": "column", "b": 500, "h": 500, "x": 0, "y": 0, "material": "C40"},
        {"id": "B1", "type": "beam", "b": 300, "h": 600, "x1": 0, "y1": 0, "x2": 6000, "y2": 0},
        {"id": "BR1", "type": "brace", "section": "H200"},       # 语义有损(SSM未建模支撑)
        {"id": "X1", "type": "damper"},                          # 也在 lossy 名单
        {"id": "Z9", "type": "外星构件"},                          # 未识别→需人工
    ], "materials": {"C40": {}}, "loads": {"dead": 6.0}}


def test_import_maps_known_types():
    ssm, rep = import_model(_external(), "ETABS-e2k(示例)")
    assert ssm["members"]["C1"]["type"] == "column"
    assert ssm["members"]["B1"]["type"] == "beam"
    assert rep["total"] == 5


def test_lossy_and_manual_flagged():
    _, rep = import_model(_external(), "YJK(示例)")
    manual_ids = {x["id"] for x in rep["manual"]}
    lossy_ids = {x["id"] for x in rep["lossy"]}
    assert "Z9" in manual_ids                                   # 未识别→人工
    assert "BR1" in lossy_ids and "X1" in lossy_ids             # 支撑/阻尼器→有损
    assert rep["clean"] is False


def test_coverage_and_transparency():
    _, rep = import_model(_external(), "PKPM(示例)")
    # 5 个构件, 未识别 1 个不计入 mapped
    assert 0 < rep["coverage"] < 1
    md = render_report(rep)
    assert "迁移诊断报告" in md and "100% 透明" in md
    assert "语义有损" in md and "需人工补充" in md


def test_imported_ssm_is_versionable():
    ssm, _ = import_model(_external(), "STAAD(示例)")
    repo = SSMRepo(); c = repo.commit(ssm, "迁移导入", "迁移工程师")
    assert repo.checkout(c)["design_context"]["imported_from"] == "STAAD(示例)"


def test_clean_import_100pct():
    ext = {"members": [{"id": "C1", "type": "column", "b": 500, "h": 500}]}
    _, rep = import_model(ext, "IFC")
    assert rep["clean"] is True and rep["coverage"] == 1.0


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
