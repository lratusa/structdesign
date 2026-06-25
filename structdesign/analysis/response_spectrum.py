"""
振型分解反应谱法（GB 50011 5.2.2）+ 振型组合（SRSS）。

各振型 j 在楼层 i 的水平地震作用：
    F_ji = α_j · γ_j · φ_ji · G_i      (G_i = m_i·g 重力荷载代表值)
振型组合(SRSS)：F_i = sqrt(Σ_j F_ji²)；层剪力为其上各层之和。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import numpy as np

from .modal import solve_shear_building, ModalResult
from ..codes import gb50011_spectrum as sp


@dataclass
class SeismicResult:
    modal: ModalResult
    alphas: List[float]
    story_forces: List[float]      # 各层 SRSS 组合地震力 (N)，自下而上
    story_shears: List[float]      # 各层剪力 (N)
    base_shear: float              # 基底剪力 (N)
    n_modes: int
    modal_floor_forces: object = None   # np数组 n×n_modes：各振型各层地震力(N)，
                                        # 用于"逐振型求构件内力再SRSS"的正确组合


def response_spectrum_analysis(masses, stiffnesses, alpha_max, Tg,
                               zeta=0.05, g=9.81, n_modes=None) -> SeismicResult:
    m = np.asarray(masses, float)
    n = len(m)
    n_modes = n if n_modes is None else min(n_modes, n)
    modal = solve_shear_building(masses, stiffnesses)
    G = m * g  # 重力荷载代表值 (N)

    alphas = []
    F_modes = np.zeros((n, n_modes))
    for j in range(n_modes):
        T = modal.periods[j]
        a = sp.alpha(T, alpha_max, Tg, zeta)
        alphas.append(a)
        phi = modal.modes[:, j]
        gamma = modal.gammas[j]
        F_modes[:, j] = a * gamma * phi * G

    # SRSS 组合楼层力
    story_forces = np.sqrt((F_modes ** 2).sum(axis=1))

    # 由楼层力按"各振型层剪力 SRSS"更严谨；此处对层剪力也用 SRSS
    shear_modes = np.zeros((n, n_modes))
    for j in range(n_modes):
        # 第 i 层剪力 = 其上(含本层)各层该振型力之和
        f = F_modes[:, j]
        shear_modes[:, j] = np.array([f[i:].sum() for i in range(n)])
    story_shears = np.sqrt((shear_modes ** 2).sum(axis=1))
    base_shear = float(story_shears[0])

    return SeismicResult(modal=modal, alphas=alphas,
                         story_forces=[float(x) for x in story_forces],
                         story_shears=[float(x) for x in story_shears],
                         base_shear=base_shear, n_modes=n_modes,
                         modal_floor_forces=F_modes)
