"""规范 DSL —— 受限声明式表达式语言（设计书 §4.1）。

只能表达：算术、比较、布尔、三元条件、查表(interp/lookup)、白名单数学函数。
**不含**：循环、函数定义、属性访问、下标、推导式、任意函数调用、import。
→ 每条规则可静态审计、可单元测试；杜绝规范条文里藏图灵完备逻辑。

用法：
    evaluate("max(0.2, 45*ft/fy)", {"ft": 1.43, "fy": 360})  -> 0.2 (若 45*ft/fy<0.2)
    evaluate("rho >= rho_min", {"rho": 0.008, "rho_min": 0.002})  -> True
"""
from __future__ import annotations
import ast
import math

# 白名单函数（纯、无副作用）
FUNCS = {
    "max": max, "min": min, "abs": abs, "round": round, "pow": pow,
    "sqrt": math.sqrt, "ceil": math.ceil, "floor": math.floor,
    "interp": lambda x, xs, ys: _interp(x, xs, ys),   # 线性插值查表
    "lookup": lambda key, keys, vals: _lookup(key, keys, vals),  # 精确查表
}

# 允许的 AST 节点类型
_ALLOWED = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.Call, ast.Name, ast.Load, ast.Constant, ast.Tuple, ast.List,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)
# 兼容旧版 ast（Num/Str/NameConstant）
for _n in ("Num", "Str", "NameConstant", "Bytes"):
    if hasattr(ast, _n):
        _ALLOWED = _ALLOWED + (getattr(ast, _n),)


class DSLError(ValueError):
    pass


def _interp(x, xs, ys):
    xs = list(xs); ys = list(ys)
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def _lookup(key, keys, vals):
    for k, v in zip(keys, vals):
        if k == key:
            return v
    raise DSLError(f"查表未命中: {key!r}")


def _validate(tree):
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise DSLError(f"DSL 不允许的语法: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:
                nm = getattr(node.func, "id", type(node.func).__name__)
                raise DSLError(f"DSL 不允许的函数调用: {nm}")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            pass  # 变量在求值时从 env 取，未定义会报 NameError


def evaluate(expr: str, env: dict):
    """求值一个 DSL 表达式。env 提供变量。返回数值/布尔。"""
    if not isinstance(expr, str):
        return expr
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise DSLError(f"DSL 语法错误: {expr!r} ({e})")
    _validate(tree)
    ns = {"__builtins__": {}}
    ns.update(FUNCS)
    ns.update(env)
    try:
        return eval(compile(tree, "<dsl>", "eval"), ns)   # noqa: S307 — 已 AST 白名单
    except NameError as e:
        raise DSLError(f"DSL 变量未定义: {e}")


def evaluate_block(assigns, env: dict) -> dict:
    """顺序执行赋值块 ["name = expr", ...]，返回更新后的环境副本。"""
    out = dict(env)
    for line in assigns or []:
        if "=" not in line:
            raise DSLError(f"赋值语句需含 '=': {line!r}")
        name, expr = line.split("=", 1)
        out[name.strip()] = evaluate(expr.strip(), out)
    return out
