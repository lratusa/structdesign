"""规范问答：附条文出处 + 无出处不作答（设计书 §4.3 二级 / §6.1 玻璃盒硬约束）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from heng.qa import ask, format_answer


def test_answer_has_provenance():
    r = ask("柱的轴压比限值是多少")
    assert r["answered"] is True
    top = r["hits"][0]
    assert top["clause"] == "6.3.6" and "轴压比" in top["title"]
    assert top["rule_id"].startswith("CN.GB50011") and top["text"]        # 附条文号+原文


def test_clause_number_query():
    r = ask("5.5.1 是什么")
    assert r["answered"] and r["hits"][0]["clause"] == "5.5.1"             # 条号直接命中


def test_min_reinforcement_query():
    r = ask("梁最小配筋率怎么算")
    ids = [h["rule_id"] for h in r["hits"]]
    assert any("8.5.1" in i for i in ids)                                 # 命中 GB50010 8.5.1
    assert any(h["mandatory"] for h in r["hits"])                         # 标注强条


def test_no_source_no_answer():
    r = ask("量子隧穿对预应力锚索的影响")     # 库中无此内容
    assert r["answered"] is False
    assert "未检索到适用条文" in r["note"]
    assert format_answer(r) == r["note"]                                  # 不编造


def test_jurisdiction_filter():
    r = ask("最小配筋", jurisdiction="EU")
    assert r["answered"] and all(h["rule_id"].startswith("EU") for h in r["hits"])


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
