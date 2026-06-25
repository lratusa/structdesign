"""
模态分析 —— 剪切层模型（layered shear building）。

楼层集中质量 m_i、层抗侧刚度 k_i，组装质量阵 M(对角) 与刚度阵 K(三对角)，
解广义特征值问题 K φ = ω² M φ，得自振周期、振型、振型参与系数。

剪切层是抗震概念设计与振型分解反应谱法的经典简化，结果可用解析解严格验证：
  - 单自由度：T = 2π√(m/k)
  - n 自由度等质量等刚度：特征值为已知封闭解
层抗侧刚度可由柱提供：k = Σ 12·E·I / h³（两端固结柱）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import numpy as np


@dataclass
class ModalResult:
    periods: List[float]              # 各阶自振周期 T (s)，由长到短
    omegas: List[float]               # 圆频率 ω (rad/s)
    modes: np.ndarray                 # 振型矩阵，列为各阶振型(已对最大分量归一)
    gammas: List[float]               # 振型参与系数 γ_j
    masses: np.ndarray
    Meff: List[float]                 # 各阶有效质量
    Mtotal: float


def story_stiffness_from_columns(E, I_total, h):
    """层抗侧刚度 k = Σ 12EI/h³（该层所有柱，两端固结）。I_total=Σ I。"""
    return 12.0 * E * I_total / h ** 3


def solve_shear_building(masses, stiffnesses) -> ModalResult:
    """masses: [m1..mn] (kg, 自下而上); stiffnesses: [k1..kn] 层抗侧刚度 (N/m)。"""
    m = np.asarray(masses, float)
    k = np.asarray(stiffnesses, float)
    n = len(m)
    # 三对角刚度阵
    K = np.zeros((n, n))
    for i in range(n):
        K[i, i] += k[i]
        if i + 1 < n:
            K[i, i] += k[i + 1]
            K[i, i + 1] -= k[i + 1]
            K[i + 1, i] -= k[i + 1]
    M = np.diag(m)

    # 广义特征值：M^-1 K
    A = np.linalg.solve(M, K)
    w2, vecs = np.linalg.eig(A)
    w2 = np.real(w2)
    vecs = np.real(vecs)
    order = np.argsort(w2)        # 升序：低频(长周期)在前
    w2 = w2[order]
    vecs = vecs[:, order]

    omegas = np.sqrt(np.clip(w2, 0, None))
    periods = [float(2 * np.pi / w) if w > 1e-9 else float("inf") for w in omegas]

    # 归一化(最大分量=1)，计算参与系数与有效质量
    ones = np.ones(n)
    gammas, Meff, modes = [], [], np.zeros((n, n))
    Mtotal = float(m.sum())
    for j in range(n):
        phi = vecs[:, j]
        if abs(phi[np.argmax(np.abs(phi))]) > 0:
            phi = phi / phi[np.argmax(np.abs(phi))]
        modes[:, j] = phi
        num = phi @ (m * ones)
        den = phi @ (m * phi)
        gamma = num / den if den != 0 else 0.0
        gammas.append(float(gamma))
        Meff.append(float(num ** 2 / den) if den != 0 else 0.0)
    return ModalResult(periods=periods, omegas=[float(x) for x in omegas],
                       modes=modes, gammas=gammas, masses=m, Meff=Meff, Mtotal=Mtotal)
