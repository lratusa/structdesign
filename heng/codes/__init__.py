"""L3 规范引擎 —— Code-as-Data。

- dsl.py        受限声明式 DSL(非图灵完备，可静态审计)
- rule.py       规则记录(rule_id/scope/formula/provenance/lineage) + 校核结果(带溯源)
- registry.py   规则注册表 + 按辖区/版本检索 + 全量校核
- jurisdiction.py 辖区解析器(确定性)：坐标/类型/委托性质 → 生效规范集
- rules_cn_gb.py 首批中国 GB 规则(由硬编码 codes 重构而来，每条附算例)
"""
