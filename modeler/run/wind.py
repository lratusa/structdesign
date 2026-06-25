"""风荷载（GB 50009-2012 第8章）—— 方案/初步设计级。

主公式：  wk(z) = βz · μs · μz · w0      (kN/m²)
楼层风力：Fi = wk(zi) · B · h_trib,i      (kN，B=迎风面宽，h_trib=楼层受风高)

诚实边界：
- μz 高度变化系数：严格按规范表 8.2.1（各类地面粗糙度 A/B/C/D 的幂律 + 下限）。
- μs 体型系数：用户输入，矩形默认 1.3（迎风 +0.8 + 背风 +0.5）；异形/群体须另定。
- βz 风振系数：H≤30m 取 1.0（规范 8.4.1 可不计风振）；H>30m 用**简化保守背景项**估计，
  **精确顺风向风振、横风向涡激、扭转风振须按 GB 50009 8.4/8.5 由商业软件复核**。
- 仅顺风向、矩形平面、刚性楼盖假定下的楼层等效静力；不含舒适度(加速度)验算。
"""
from __future__ import annotations

# 地面粗糙度: (系数c, 指数2α, μz 下限)  —— μz = c·(z/10)^(2α)，floor 取下限
TERRAIN = {
    "A": (1.284, 0.24, 1.09),   # 海岸/海面/海岛/湖岸
    "B": (1.000, 0.30, 1.00),   # 田野/乡村/丛林/小城镇（默认）
    "C": (0.544, 0.44, 0.65),   # 有密集建筑群的城市市区
    "D": (0.262, 0.60, 0.51),   # 有密集高层的大城市市区
}
I10 = {"A": 0.12, "B": 0.14, "C": 0.23, "D": 0.39}   # 10m 处湍流度(8.4.4)
PEAK_G = 2.5                                          # 峰值因子


def mu_z(terrain: str, z: float) -> float:
    """风压高度变化系数 μz（GB 50009 表8.2.1），z 单位 m。"""
    c, e, lo = TERRAIN.get(terrain, TERRAIN["B"])
    z = max(z, 5.0)
    return max(c * (z / 10.0) ** e, lo)


def beta_z(H: float, z: float, terrain: str = "B") -> float:
    """风振系数 βz。H≤30m 取 1.0（规范8.4.1可不计风振）；
    H>30m 用**简化估计** 1+2·g·I10·(z/H)（含背景+部分共振放大量级，下限 1.3）。
    注意：这是量级估计而非精确值；高柔结构精确顺风向风振须按 GB 50009 8.4 由商业软件复核。"""
    if H <= 30.0:
        return 1.0
    return max(1.0 + 2.0 * PEAK_G * I10.get(terrain, 0.14) * (z / max(H, 1e-6)), 1.3)


def _plan_extent(project):
    xs, ys = [], []
    for f in project.level_floors():
        for c in f.columns:
            xs.append(c.x); ys.append(c.y)
        for w in f.walls:
            xs += [w.x1, w.x2]; ys += [w.y1, w.y2]
        for b in f.beams:
            xs += [b.x1, b.x2]; ys += [b.y1, b.y2]
    if not xs:
        return 0.0, 0.0
    return (max(xs) - min(xs)), (max(ys) - min(ys))   # Lx, Ly (mm)


def wind_story_forces(project, direction: str = "x"):
    """返回 (forces, info)。
    forces = {z_mm: Fi_kN}  各楼层等效风力（迎风面，集中到楼层标高）。
    info   = dict(H, width, w0, terrain, mu_s, base_shear, overturning, per_floor[list])。
    direction='x' → 风沿 X 吹，迎风面宽 = Y 向平面尺寸 Ly。"""
    w = project.wind
    if not getattr(w, "enabled", True):
        return {}, dict(H=0.0, width=0.0, w0=0.0, terrain=w.terrain, mu_s=w.mu_s,
                        base_shear=0.0, overturning=0.0, per_floor=[])
    zs = project.elevations()                     # [0, z1, ...] mm
    if len(zs) < 2:                               # 无楼层
        return {}, dict(H=0.0, width=0.0, w0=w.w0, terrain=w.terrain, mu_s=w.mu_s,
                        base_shear=0.0, overturning=0.0, per_floor=[])
    H = zs[-1] / 1000.0                            # 总高 m
    Lx, Ly = _plan_extent(project)
    width = (Ly if direction == "x" else Lx) / 1000.0     # 迎风面宽 m
    forces, per = {}, []
    n = len(zs)
    for i in range(1, n):
        z_mm = zs[i]
        z = z_mm / 1000.0
        below = (zs[i] - zs[i - 1]) / 2.0 / 1000.0
        above = (zs[i + 1] - zs[i]) / 2.0 / 1000.0 if i + 1 < n else 0.0
        h_trib = below + above
        wk = beta_z(H, z, w.terrain) * w.mu_s * mu_z(w.terrain, z) * w.w0   # kN/m²
        Fi = wk * width * h_trib                                            # kN
        forces[z_mm] = Fi
        per.append(dict(z=z_mm, wk=wk, F=Fi, mu_z=mu_z(w.terrain, z),
                        beta_z=beta_z(H, z, w.terrain), h_trib=h_trib))
    base = sum(forces.values())
    over = sum(F * (z_mm / 1000.0) for z_mm, F in forces.items())           # kN·m
    info = dict(H=H, width=width, w0=w.w0, terrain=w.terrain, mu_s=w.mu_s,
                base_shear=base, overturning=over, per_floor=per)
    return forces, info
