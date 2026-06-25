"""
GB 50011-2010(2016) 地震影响系数曲线 α(T)（规范 5.1.5）。

参数：αmax(水平地震影响系数最大值，按设防烈度/多遇罕遇查 5.1.4-1)，
      Tg(特征周期，按场地类别与设计地震分组查 5.1.4-2)，ζ(阻尼比，默认0.05)。
"""
from __future__ import annotations


def damping_params(zeta: float = 0.05):
    """阻尼调整系数 (规范 5.1.5)。返回 (γ, η1, η2)。ζ=0.05 时 (0.9, 0.02, 1.0)。"""
    gamma = 0.9 + (0.05 - zeta) / (0.3 + 6 * zeta)
    eta1 = 0.02 + (0.05 - zeta) / (4 + 32 * zeta)
    eta1 = max(eta1, 0.0)
    eta2 = 1 + (0.05 - zeta) / (0.08 + 1.6 * zeta)
    eta2 = max(eta2, 0.55)
    return gamma, eta1, eta2


def alpha(T: float, alpha_max: float, Tg: float, zeta: float = 0.05) -> float:
    """地震影响系数 α(T)。分段：直线上升段 / 平台段 / 曲线下降段 / 直线下降段。"""
    gamma, eta1, eta2 = damping_params(zeta)
    if T < 0:
        T = 0.0
    if T <= 0.1:
        return (0.45 + (eta2 - 0.45) * (T / 0.1)) * alpha_max
    elif T <= Tg:
        return eta2 * alpha_max
    elif T <= 5 * Tg:
        return (Tg / T) ** gamma * eta2 * alpha_max
    elif T <= 6.0:
        return (eta2 * 0.2 ** gamma - eta1 * (T - 5 * Tg)) * alpha_max
    else:
        # 6s 以外按 6s 取值（规范适用范围内）
        return (eta2 * 0.2 ** gamma - eta1 * (6.0 - 5 * Tg)) * alpha_max


# 常用 αmax (规范表5.1.4-1)
ALPHA_MAX = {
    ("多遇", "6度"): 0.04, ("多遇", "7度"): 0.08, ("多遇", "7度0.15g"): 0.12,
    ("多遇", "8度"): 0.16, ("多遇", "8度0.30g"): 0.24, ("多遇", "9度"): 0.32,
    ("罕遇", "6度"): 0.28, ("罕遇", "7度"): 0.50, ("罕遇", "7度0.15g"): 0.72,
    ("罕遇", "8度"): 0.90, ("罕遇", "8度0.30g"): 1.20, ("罕遇", "9度"): 1.40,
}

# 特征周期 Tg (规范表5.1.4-2)，[设计地震分组][场地类别]
TG = {
    1: {"I0": 0.20, "I1": 0.25, "II": 0.35, "III": 0.45, "IV": 0.65},
    2: {"I0": 0.25, "I1": 0.30, "II": 0.40, "III": 0.55, "IV": 0.75},
    3: {"I0": 0.30, "I1": 0.35, "II": 0.45, "III": 0.65, "IV": 0.90},
}
