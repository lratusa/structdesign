"""建模器数据模型（纯 dataclass，无 Qt 依赖，可 headless 测试）。

标准层范式：一个标准层平面(轴网/柱/梁/墙/板荷载) + 楼层表(层高×层数) → 竖向拉伸成 3D。
工程文件 .sdproj 为 JSON。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List
import json


@dataclass
class Column:
    x: float; y: float; b: float = 500; h: float = 500; mat: str = "C40"


@dataclass
class Beam:
    x1: float; y1: float; x2: float; y2: float; b: float = 300; h: float = 600; mat: str = "C30"


@dataclass
class Wall:
    x1: float; y1: float; x2: float; y2: float; t: float = 400; mat: str = "C40"


@dataclass
class SlabLoad:
    dead: float = 6.0; live: float = 2.5


@dataclass
class Slab:
    """矩形楼板，由对角两点定义；t 板厚 mm。荷载用楼层板荷载(floor.slab)。"""
    x1: float; y1: float; x2: float; y2: float; t: float = 120; mat: str = "C30"


@dataclass
class Opening:
    """板洞(打孔)：平面矩形洞。kind: 板洞/管井/电梯井/梯井。"""
    x1: float; y1: float; x2: float; y2: float; kind: str = "板洞"


@dataclass
class StairPlacement:
    """楼梯布置区(矩形)；run='x'/'y' 梯跑方向；其下自动视为梯井(板洞)。"""
    x1: float; y1: float; x2: float; y2: float; run: str = "x"


@dataclass
class Joint:
    """结构缝(线)：kind 伸缩缝/沉降缝/抗震缝；width 缝宽 mm。"""
    x1: float; y1: float; x2: float; y2: float; kind: str = "抗震缝"; width: float = 100


@dataclass
class WallOpening:
    """墙洞/结构洞：平面上沿墙的一段(x1,y1)-(x2,y2) 标记洞宽；h 洞高、sill 窗台高(离楼面) mm。"""
    x1: float; y1: float; x2: float; y2: float; h: float = 1500; sill: float = 900


@dataclass
class Storey:
    height: float = 3600; count: int = 1; floor_id: str = ""   # ""=用默认标准层(Project.floor)


@dataclass
class Seismic:
    alpha_max: float = 0.16; Tg: float = 0.45; grade: str = "二级"; n_modes: int = 12
    vertical: bool = False     # 是否计算竖向地震(8/9度、长悬挑/大跨/转换需计，GB 50011 5.3)
    diaphragm: str = "rigid"   # 楼盖假定: rigid(刚性,默认) | semi_rigid | elastic(柔性,出柔性周期对比)


@dataclass
class Wind:
    """风荷载参数(GB 50009-2012 第8章)。enabled=False 时不参与计算。"""
    enabled: bool = True
    w0: float = 0.40          # 基本风压 kN/m²(50年一遇，按当地)
    terrain: str = "B"        # 地面粗糙度 A/B/C/D
    mu_s: float = 1.3         # 风荷载体型系数(矩形≈迎风0.8+背风0.5)


@dataclass
class Thermal:
    """温度作用参数(GB 50009 第9章)。默认关闭(有伸缩缝的常规建筑可不计)。"""
    enabled: bool = False
    dT: float = 25.0          # 均匀温差 ΔT (°C，升降温取大)
    alpha: float = 1.0e-5     # 线膨胀系数 (混凝土≈1.0e-5 /°C)


@dataclass
class Basement:
    """地下室参数(地下室外墙水土压力 + 抗浮)。默认关闭。"""
    enabled: bool = False
    n_levels: int = 1          # 地下室层数
    height: float = 3600.0     # 每层层高 mm
    wall_t: float = 300.0      # 外墙厚 mm
    soil_gamma: float = 18.0   # 土重度 kN/m³
    K0: float = 0.5            # 静止土压力系数
    water_depth: float = 1.0   # 地下水位埋深(地面以下 m；≥总深则无水)
    surcharge: float = 10.0    # 地面活荷载侧压(kPa)


@dataclass
class DesignPolicy:
    """设计规则策略：贯穿**计算 + 出图**的可配置规则，供自然语言/LLM 指令层设置。
    新增规则在此加字段，并在 analyze / dxf_export 中读取生效。"""
    beam_rebar_merge: str = "none"   # 梁纵筋归并: none(逐根) | envelope(同编号组取大包罗，便于施工)
    prefab_joint: bool = False       # 装配式分缝(接口预留，后续填充分缝逻辑)


@dataclass
class Grid:
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)


@dataclass
class StandardFloor:
    columns: List[Column] = field(default_factory=list)
    beams: List[Beam] = field(default_factory=list)
    walls: List[Wall] = field(default_factory=list)
    slabs: List[Slab] = field(default_factory=list)        # 楼板布置(可选)
    openings: List[Opening] = field(default_factory=list)  # 板洞(打孔)
    wall_openings: List[WallOpening] = field(default_factory=list)  # 墙洞/结构洞(开窗)
    stairs_placed: List[StairPlacement] = field(default_factory=list)  # 楼梯布置
    slab: SlabLoad = field(default_factory=SlabLoad)        # 整层板荷载(kN/m²)


def _sf_to_dict(fl: StandardFloor) -> dict:
    return {
        "columns": [asdict(c) for c in fl.columns],
        "beams": [asdict(b) for b in fl.beams],
        "walls": [asdict(w) for w in fl.walls],
        "slabs": [asdict(s) for s in fl.slabs],
        "openings": [asdict(o) for o in fl.openings],
        "wall_openings": [asdict(o) for o in fl.wall_openings],
        "stairs_placed": [asdict(s) for s in fl.stairs_placed],
        "slab": asdict(fl.slab),
    }


def _sf_from_dict(fl: dict) -> StandardFloor:
    return StandardFloor(
        columns=[Column(**c) for c in fl.get("columns", [])],
        beams=[Beam(**b) for b in fl.get("beams", [])],
        walls=[Wall(**w) for w in fl.get("walls", [])],
        slabs=[Slab(**s) for s in fl.get("slabs", [])],
        openings=[Opening(**o) for o in fl.get("openings", [])],
        wall_openings=[WallOpening(**o) for o in fl.get("wall_openings", [])],
        stairs_placed=[StairPlacement(**s) for s in fl.get("stairs_placed", [])],
        slab=SlabLoad(**fl["slab"]),
    )


@dataclass
class Project:
    grid: Grid = field(default_factory=Grid)
    floor: StandardFloor = field(default_factory=StandardFloor)   # 默认标准层
    floors: dict = field(default_factory=dict)                    # {id: StandardFloor} 额外标准层(大底盘/多塔)
    active_floor: str = ""                                        # 当前编辑的标准层 id（""=默认 floor）
    storeys: List[Storey] = field(default_factory=lambda: [Storey()])
    seismic: Seismic = field(default_factory=Seismic)
    wind: Wind = field(default_factory=Wind)                # 风荷载参数
    thermal: Thermal = field(default_factory=Thermal)       # 温度作用参数
    basement: Basement = field(default_factory=Basement)    # 地下室参数
    policy: DesignPolicy = field(default_factory=DesignPolicy)   # 设计规则(LLM 指令可改)
    region: str = "national"    # 地区标准 key(national/beijing/...)；见 modeler/regions.py
    fak: float = 200.0          # 地基承载力特征值 kPa（独立基础设计用）
    joints: List[Joint] = field(default_factory=list)      # 结构缝
    underlay: dict = field(default_factory=dict)

    def total_floors(self) -> int:
        return sum(s.count for s in self.storeys)

    def floor_for_storey(self, storey) -> "StandardFloor":
        if storey.floor_id and storey.floor_id in self.floors:
            return self.floors[storey.floor_id]
        return self.floor

    def level_floors(self) -> List["StandardFloor"]:
        """各楼层(1..N)对应的标准层平面，顺序与 elevations()[1:] 对齐。"""
        out = []
        for s in self.storeys:
            for _ in range(int(s.count)):
                out.append(self.floor_for_storey(s))
        return out

    def edit_floor(self) -> "StandardFloor":
        """当前编辑的标准层。"""
        if self.active_floor and self.active_floor in self.floors:
            return self.floors[self.active_floor]
        return self.floor

    def elevations(self) -> List[float]:
        """[0(基底), z1, z2, ...]，长度 = 总层数 + 1。"""
        zs = [0.0]
        for s in self.storeys:
            for _ in range(int(s.count)):
                zs.append(zs[-1] + s.height)
        return [int(z) if float(z).is_integer() else z for z in zs]

    def to_dict(self) -> dict:
        return {
            "grid": asdict(self.grid),
            "floor": _sf_to_dict(self.floor),
            "floors": {k: _sf_to_dict(v) for k, v in self.floors.items()},
            "active_floor": self.active_floor,
            "storeys": [asdict(s) for s in self.storeys],
            "seismic": asdict(self.seismic),
            "wind": asdict(self.wind),
            "thermal": asdict(self.thermal),
            "basement": asdict(self.basement),
            "policy": asdict(self.policy),
            "region": self.region,
            "fak": self.fak,
            "joints": [asdict(j) for j in self.joints],
            "underlay": self.underlay,
        }

    @staticmethod
    def from_dict(d: dict) -> "Project":
        return Project(
            grid=Grid(**d["grid"]),
            floor=_sf_from_dict(d["floor"]),
            floors={k: _sf_from_dict(v) for k, v in d.get("floors", {}).items()},
            active_floor=d.get("active_floor", ""),
            storeys=[Storey(**s) for s in d["storeys"]],
            seismic=Seismic(**d["seismic"]),
            wind=Wind(**d.get("wind", {})),
            thermal=Thermal(**d.get("thermal", {})),
            basement=Basement(**d.get("basement", {})),
            policy=DesignPolicy(**d.get("policy", {})),
            region=d.get("region", "national"),
            fak=d.get("fak", 200.0),
            joints=[Joint(**j) for j in d.get("joints", [])],
            underlay=d.get("underlay", {}),
        )

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "Project":
        with open(path, encoding="utf-8") as f:
            return Project.from_dict(json.load(f))
