"""命令层 —— 面向自然语言/LLM 控制的统一接口。

设计目标（用户 2026-06-25）：未来接 LLM API，用自然语言下达指令，同时作用于**图面 + 计算**。
例：「把所有窗户从中心扩大200」「梁纵筋取大包罗」「自动装配式分缝」。

架构：
- 每条指令 = 一个**已注册命令**：名称 + 描述 + 参数规格(类型/默认/说明) + 执行函数。
- LLM 侧：`to_tool_schema()` 输出 Anthropic tool-use 的 JSON 工具列表 → LLM 解析自然语言 → 选命令+填参。
- 执行侧：`run_command(project, name, **params)` 分发执行 → 改写 project（几何/规则）→ 返回中文摘要。
- 几何类命令直接改 `project`（柱/梁/墙/洞/窗）；规则类命令改 `project.policy`(DesignPolicy)，
  由 analyze / dxf_export 在计算与出图时读取生效。

新增命令：用 `@command(name, description, params=...)` 装饰一个 `func(project, **params)->str`。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class CommandSpec:
    name: str
    description: str
    params: Dict[str, dict]          # {param: {"type","default","doc","enum"?}}
    func: Callable

    def tool_schema(self) -> dict:
        """转 Anthropic tool-use 工具定义。"""
        props, required = {}, []
        type_map = {int: "integer", float: "number", str: "string", bool: "boolean"}
        for pname, spec in self.params.items():
            t = spec.get("type", str)
            p = {"type": type_map.get(t, "string"), "description": spec.get("doc", "")}
            if "enum" in spec:
                p["enum"] = list(spec["enum"])
            props[pname] = p
            if "default" not in spec:
                required.append(pname)
        return {"name": self.name, "description": self.description,
                "input_schema": {"type": "object", "properties": props, "required": required}}


REGISTRY: Dict[str, CommandSpec] = {}


def command(name: str, description: str, params: Dict[str, dict] = None):
    def deco(func):
        REGISTRY[name] = CommandSpec(name, description, params or {}, func)
        return func
    return deco


def list_commands() -> List[CommandSpec]:
    return list(REGISTRY.values())


def to_tool_schema() -> List[dict]:
    """LLM tool-use 工具列表（直接喂给 Anthropic Messages API 的 tools 参数）。"""
    return [c.tool_schema() for c in REGISTRY.values()]


def run_command(project, name: str, **params) -> str:
    """执行命令，返回中文摘要。未知命令/参数错误抛 ValueError/TypeError。"""
    if name not in REGISTRY:
        raise ValueError(f"未知命令: {name}（可用: {', '.join(REGISTRY)}）")
    spec = REGISTRY[name]
    kw = {}
    for pname, pspec in spec.params.items():
        if pname in params:
            kw[pname] = params[pname]
        elif "default" in pspec:
            kw[pname] = pspec["default"]
        else:
            raise TypeError(f"命令 {name} 缺少必填参数: {pname}")
    return spec.func(project, **kw)


# ---------------- 内置命令 ----------------

@command(
    "scale_openings",
    "按指定增量从中心扩大/缩小洞口尺寸（窗洞 window=墙洞，板洞 slab_opening）。delta 为每个方向总增量(mm)，从中心对称。",
    params={
        "delta": {"type": float, "doc": "尺寸总增量(mm)，正为扩大、负为缩小，从中心对称分配"},
        "target": {"type": str, "default": "window", "enum": ["window", "slab_opening"],
                   "doc": "作用对象：window=墙洞/开窗，slab_opening=板洞"},
    },
)
def scale_openings(project, delta, target="window"):
    fl = project.edit_floor()
    n = 0
    half = delta / 2.0
    if target == "window":
        for o in fl.wall_openings:
            L = ((o.x2 - o.x1) ** 2 + (o.y2 - o.y1) ** 2) ** 0.5 or 1.0
            ux, uy = (o.x2 - o.x1) / L, (o.y2 - o.y1) / L
            o.x1 -= ux * half; o.y1 -= uy * half          # 沿洞口走向两端各扩 half
            o.x2 += ux * half; o.y2 += uy * half
            o.h = max(o.h + delta, 100.0)                 # 高度增 delta
            o.sill = max(o.sill - half, 0.0)              # 窗台下降 half(保持中心)
            n += 1
    else:
        for o in fl.openings:
            o.x1 -= half; o.y1 -= half; o.x2 += half; o.y2 += half
            n += 1
    verb = "扩大" if delta >= 0 else "缩小"
    return f"已从中心{verb} {n} 个{'窗洞' if target=='window' else '板洞'}，每个尺寸增量 {delta:.0f}mm。"


@command(
    "set_slab_load",
    "设置当前标准层所有楼板的楼面荷载（恒载/静荷载、活载/动荷载，kN/m²）。",
    params={
        "dead": {"type": float, "doc": "恒载(静荷载) kN/m²"},
        "live": {"type": float, "doc": "活载(动荷载) kN/m²"},
    },
)
def set_slab_load(project, dead, live):
    from .project import SlabLoad
    project.edit_floor().slab = SlabLoad(float(dead), float(live))
    return f"已设标准层楼面荷载：恒载 {dead} kN/m²、活载 {live} kN/m²（下次计算生效）。"


@command(
    "set_region",
    "套用地区标准（国标/地方标准），自动填入该地区的抗震 αmax/Tg、基本风压 w0、地面粗糙度。",
    params={
        "region": {"type": str, "default": "national", "enum": ["national", "beijing"],
                   "doc": "地区 key：national=国标通用，beijing=北京（后续可加其它城市）"},
    },
)
def set_region(project, region="national"):
    from .regions import apply_region
    return apply_region(project, region)


@command(
    "set_design_rule",
    "设置贯穿计算与出图的设计规则。梁纵筋取大包罗(envelope)=同截面梁统一按最大配筋，便于施工。",
    params={
        "beam_rebar_merge": {"type": str, "default": "none", "enum": ["none", "envelope"],
                             "doc": "梁纵筋归并规则：none=逐根设计；envelope=同截面组取大包罗"},
        "prefab_joint": {"type": bool, "default": False, "doc": "是否启用装配式分缝(接口预留)"},
    },
)
def set_design_rule(project, beam_rebar_merge="none", prefab_joint=False):
    project.policy.beam_rebar_merge = beam_rebar_merge
    project.policy.prefab_joint = bool(prefab_joint)
    parts = []
    if beam_rebar_merge == "envelope":
        parts.append("梁纵筋取大包罗(同截面统一最大配筋)")
    if prefab_joint:
        parts.append("装配式分缝(预留)")
    return "已设设计规则：" + ("、".join(parts) if parts else "默认(逐根设计)") + "。下次计算/出图生效。"


# ---------------- 自然语言意图解析（本地，无需联网/API Key） ----------------

def _nums(text):
    return [float(x) for x in re.findall(r"-?\d+\.?\d*", text)]


def local_intents(text: str):
    """把一句中文指令解析为 [(命令名, 参数dict), ...]（本地规则，离线可用）。
    覆盖常见意图：板荷载、窗洞/板洞缩放、梁取大包罗、地区切换、装配分缝。无法识别返回 []。"""
    t = text.strip()
    out = []
    # 楼板荷载：静/恒 + 活/动
    if "板" in t and ("荷载" in t or "荷" in t or "载" in t):
        m_d = re.search(r"(静|恒)[载荷]*\s*[:：]?\s*(-?\d+\.?\d*)", t)
        m_l = re.search(r"(活|动)[载荷]*\s*[:：]?\s*(-?\d+\.?\d*)", t)
        if m_d or m_l:
            dead = float(m_d.group(2)) if m_d else 5.0
            live = float(m_l.group(2)) if m_l else 2.0
            return [("set_slab_load", {"dead": dead, "live": live})]
    # 窗洞 / 板洞 缩放
    if "窗" in t or "洞" in t:
        ns = _nums(t)
        d = ns[0] if ns else 200.0
        if "缩" in t or "减" in t:
            d = -abs(d)
        target = "slab_opening" if "板洞" in t else "window"
        return [("scale_openings", {"delta": d, "target": target})]
    # 梁纵筋取大包罗
    if "梁" in t and ("包罗" in t or "取大" in t or "归并" in t):
        return [("set_design_rule", {"beam_rebar_merge": "envelope"})]
    # 地区标准
    if "北京" in t:
        return [("set_region", {"region": "beijing"})]
    if "国标" in t or "通用" in t:
        return [("set_region", {"region": "national"})]
    # 装配式分缝
    if "分缝" in t or "装配" in t:
        return [("set_design_rule", {"prefab_joint": True})]
    return out


def run_nl(project, text: str):
    """本地自然语言执行：解析→逐条执行→返回摘要列表。无法识别返回提示。"""
    intents = local_intents(text)
    if not intents:
        return ["未能识别该指令。可尝试：『所有窗户从中心扩大200』『标准层所有板 恒载5 活载2』"
                "『梁纵筋取大包罗』『改用北京地标』。或在设置里填 API Key 启用 LLM 智能对话。"]
    msgs = []
    for name, params in intents:
        try:
            msgs.append(run_command(project, name, **params))
        except Exception as e:
            msgs.append(f"[{name}] 执行失败：{e}")
    return msgs


# ---------------- LLM 智能对话（可选，需 anthropic + API Key） ----------------

SYSTEM_PROMPT = (
    "你是结构设计建模软件 structdesign 的助手。用户用中文下达建模/设计指令，"
    "你必须通过提供的工具(tools)来执行，不要编造未提供的能力。"
    "执行后用简洁中文确认所做修改。单位：荷载 kN/m²，尺寸 mm。"
)


def llm_available():
    import os
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def run_llm(project, text: str, history=None, model=None):
    """用 LLM(Anthropic Messages API) + 工具调用执行自然语言指令。返回 (回复文本, 摘要列表)。
    需 `pip install anthropic` 且环境变量 ANTHROPIC_API_KEY。
    模型可用环境变量 STRUCTDESIGN_LLM_MODEL 覆盖。"""
    import os
    import anthropic
    model = model or os.environ.get("STRUCTDESIGN_LLM_MODEL", "claude-opus-4-8")
    client = anthropic.Anthropic()
    tools = to_tool_schema()
    msgs = list(history or []) + [{"role": "user", "content": text}]
    summaries = []
    final = ""
    for _ in range(6):
        resp = client.messages.create(model=model, max_tokens=1024,
                                      system=SYSTEM_PROMPT, tools=tools, messages=msgs)
        msgs.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type == "text":
                final += block.text
            elif block.type == "tool_use":
                try:
                    s = run_command(project, block.name, **block.input)
                except Exception as e:
                    s = f"执行失败：{e}"
                summaries.append(s)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": s})
        if not tool_results:
            break
        msgs.append({"role": "user", "content": tool_results})
    return final.strip(), summaries
