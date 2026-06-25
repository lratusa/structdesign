"""
ETABS OAPI 适配器（骨架）。

ETABS 通过 OAPI(COM/.NET) 暴露建模、分析、取结果的完整 API。本适配器演示
"翻译模型→运行分析→提取内力→映射回 MemberForces" 的完整结构。真正运行需要：
  - Windows + 已安装 ETABS（含其 OAPI / CSI API DLL）
  - pip install comtypes  （或 pythonnet 走 .NET 程序集）

运行环境就绪后，把下方 `_connect` 内的占位换成真实连接即可，闭环代码无需改动。
"""
from __future__ import annotations
from typing import Dict

from ..frame_spec import FrameSpec, MemberForces


class EtabsAnalyzer:
    name = "ETABS (OAPI)"

    def __init__(self, attach_to_running: bool = True, model_path: str = ""):
        self.attach_to_running = attach_to_running
        self.model_path = model_path
        self._sap = None  # SapModel

    # --------------------------------------------------------------
    def _connect(self):
        """连接 ETABS 并取得 SapModel。需要 comtypes + 本机 ETABS。"""
        try:
            import comtypes.client  # noqa
        except ImportError as e:
            raise RuntimeError(
                "未安装 comtypes，且需在装有 ETABS 的 Windows 上运行。"
                "pip install comtypes；或改用 InternalFrameAnalyzer。") from e
        import comtypes.client
        helper = comtypes.client.CreateObject("ETABSv1.Helper")
        helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
        if self.attach_to_running:
            etabs = helper.GetObject("CSI.ETABS.API.ETABSObject")
        else:
            etabs = helper.CreateObjectProgID("CSI.ETABS.API.ETABSObject")
            etabs.ApplicationStart()
        self._sap = etabs.SapModel
        self._sap.InitializeNewModel()
        if self.model_path:
            self._sap.File.OpenFile(self.model_path)

    # --------------------------------------------------------------
    def _push_model(self, spec: FrameSpec):
        """FrameSpec → ETABS 模型（关键 OAPI 调用示意）。"""
        sap = self._sap
        sap.SetPresentUnits(6)  # N_mm_C
        # 节点 / 框架对象
        name_map = {}
        for mid, (ni, nj, sec, w) in spec.members.items():
            x1, y1, _ = spec.nodes[ni]
            x2, y2, _ = spec.nodes[nj]
            # 平面框架放在 XZ 平面：z 取竖向
            ret, nm = sap.FrameObj.AddByCoord(x1, 0, y1, x2, 0, y2, "", "Default", mid)
            name_map[mid] = nm
            # 定义并指定矩形截面属性
            prop = f"{sec.kind}_{int(sec.b)}x{int(sec.h)}"
            sap.PropFrame.SetRectangle(prop, sec.concrete, sec.h, sec.b)
            sap.FrameObj.SetSection(nm, prop)
            if w:
                # 均布荷载(竖向重力)，荷载工况 DEAD
                sap.FrameObj.SetLoadDistributed(nm, "DEAD", 1, 10, 0, 1, w, w)
        # 约束、节点荷载等同理：PointObj.SetRestraint / SetLoadForce ...
        return name_map

    # --------------------------------------------------------------
    def analyze(self, spec: FrameSpec) -> Dict[str, MemberForces]:
        if self._sap is None:
            self._connect()
        name_map = self._push_model(spec)
        sap = self._sap
        sap.Analyze.RunAnalysis()
        sap.Results.Setup.DeselectAllCasesAndCombosForOutput()
        sap.Results.Setup.SetCaseSelectedForOutput("DEAD")

        out: Dict[str, MemberForces] = {}
        for mid, nm in name_map.items():
            # FrameForce 返回沿杆长各站点的 P,V2,V3,T,M2,M3
            res = sap.Results.FrameForce(nm, 0)
            # res = (NumberResults, Obj, ObjSta, Elm, ElmSta, LoadCase,
            #        StepType, StepNum, P, V2, V3, T, M2, M3, ret)
            P, V2, M3 = res[8], res[9], res[13]
            n = len(P)
            out[mid] = MemberForces(
                Mi=M3[0], Mj=M3[-1], M_mid=M3[n // 2],
                Vi=V2[0], Vj=V2[-1], N_axial=-P[0],  # ETABS P 拉为正→压为正取负
            )
        return out
