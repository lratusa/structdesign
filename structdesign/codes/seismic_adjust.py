"""
能力设计内力调整 —— 强柱弱梁 / 强剪弱弯（GB 50011）。

本质：控制塑性铰出现位置（梁端先于柱端、弯曲先于剪切）。规范用放大系数实现。
本版采用规范放大系数法（简化，未做"实配反算"的一级特例），所有系数可追溯。

  - 强柱弱梁  柱端弯矩放大 ηc   (GB 50011 6.2.2)
  - 强剪弱弯  梁端剪力放大 ηvb  (GB 50011 6.2.4)
  - 强剪弱弯  柱端剪力放大 ηvc  (GB 50011 6.2.5)
"""
from __future__ import annotations

# 柱端弯矩增大系数 ηc（框架结构，简化）
ETA_C = {"一级": 1.7, "二级": 1.5, "三级": 1.3, "四级": 1.2, None: 1.0}
# 梁端剪力增大系数 ηvb
ETA_VB = {"一级": 1.3, "二级": 1.2, "三级": 1.1, "四级": 1.0, None: 1.0}
# 柱端剪力增大系数 ηvc
ETA_VC = {"一级": 1.4, "二级": 1.2, "三级": 1.1, "四级": 1.0, None: 1.0}


def column_moment_magnify(M, seismic_grade):
    """强柱弱梁：柱端弯矩放大。返回 (M_adj, η)。"""
    eta = ETA_C.get(seismic_grade, 1.0)
    return M * eta, eta


def beam_shear_magnify(V, seismic_grade):
    """强剪弱弯：梁端剪力放大。返回 (V_adj, η)。"""
    eta = ETA_VB.get(seismic_grade, 1.0)
    return V * eta, eta


def column_shear_magnify(V, seismic_grade):
    """强剪弱弯：柱端剪力放大。返回 (V_adj, η)。"""
    eta = ETA_VC.get(seismic_grade, 1.0)
    return V * eta, eta
