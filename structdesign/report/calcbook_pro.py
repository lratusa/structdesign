"""
专业结构计算书生成器（审图风格）。

输入一个结构化数据字典(由 design_project_3d 收集)，输出完整、规范、可审查的
结构计算书 markdown：工程概况 / 设计依据 / 材料与荷载 / 计算模型与方法 /
周期振型与地震作用 / 位移验算 / 整体稳定 / 构件配筋全表 / 规范指标汇总 / 结论。
逐项标注规范条文出处。
"""
from __future__ import annotations
from datetime import date
from typing import Dict, List


def render(d: Dict) -> str:
    L: List[str] = []
    p = d["project"]
    s = d["seismic"]
    L.append(f"# {p['name']}　结构计算书")
    L.append("")
    L.append(f"编制日期：{date.today().isoformat()}　　计算软件：structdesign v{d.get('version','0.1')}")
    L.append("")
    L.append("---")

    # 一、工程概况
    L.append("\n## 一、工程概况\n")
    L.append(f"本工程为 {p['type']}，平面 {p['nx']}×{p['ny']} 跨（柱距 {p['bx']/1000:.1f}×{p['by']/1000:.1f} m），"
             f"共 {p['nz']} 层，层高 {p['hz']/1000:.1f} m，结构总高度 {p['nz']*p['hz']/1000:.1f} m。")
    L.append(f"抗侧力体系：{p['system']}。" + (f"核心墙 {p['n_walls']} 处。" if p['n_walls'] else ""))
    L.append("")
    fig = d.get("figures", {})
    if fig.get("plan"):
        L.append(f"![图1　结构标准层平面布置简图]({fig['plan']})")
        L.append("")
    if fig.get("model"):
        L.append(f"![图2　三维结构计算模型（轴测）]({fig['model']})")
        L.append("")

    # 二、设计依据
    L.append("## 二、设计依据\n")
    if d.get("region") and d.get("region") != "国标(GB·通用)":
        L.append(f"- 地区标准：**{d['region']}**（在国标基础上按地方标准/区划取参数）")
    for code in d["codes"]:
        L.append(f"- {code}")
    L.append("")

    # 三、材料
    L.append("## 三、材料\n")
    L.append(f"- 混凝土：柱/墙 {p['concrete_col']}，梁/板 {p['concrete_beam']}")
    L.append(f"- 钢筋：纵筋 HRB400，箍筋 HPB300/HRB400")
    L.append("")

    # 四、荷载与地震参数
    L.append("## 四、荷载与地震参数\n")
    L.append(f"- 楼面恒载 {p['dead']} kN/m²，活载 {p['live']} kN/m²；"
             f"荷载组合按 GB 50009（γG=1.3，γQ=1.5）。")
    L.append("- **活荷载折减**：设计墙/柱/基础时，其上各层活荷载按计算截面以上层数折减"
             "（GB 50009 5.1.2，第1类，1层1.00 / 2~3层0.85 / 4~5层0.70 / 6~8层0.65 / "
             "9~20层0.60 / >20层0.55）；楼面梁按从属面积>25㎡折减0.9（5.1.1）。")
    L.append(f"- 抗震设防：地震影响系数最大值 αmax={s['alpha_max']}，特征周期 Tg={s['Tg']} s，"
             f"抗震等级 {p['seismic_grade']}，阻尼比 ζ={s.get('zeta',0.05)}。")
    L.append(f"- 重力荷载代表值：每层 {s['mass']/1e3:.0f} t。")
    L.append("")

    # 五、计算模型与方法
    L.append("## 五、计算模型与方法\n")
    L.append("采用三维空间杆系模型，每节点 6 个自由度，梁柱为空间梁单元（含双向弯曲与扭转），"
             "剪力墙采用等效宽柱模拟；楼盖按平面内刚性假定（每层 3 个自由度 UX/UY/RZ）。")
    L.append("水平地震作用采用**振型分解反应谱法**（GB 50011 5.2.2），各振型反应按"
             "**完全二次型 CQC 法**组合（考虑平动-扭转耦联），两个方向按"
             "0.85 规则组合（GB 50011 5.2.3）。竖向荷载下另计 P-Δ 二阶效应与整体稳定。")
    if d.get("diaphragm") and d.get("diaphragm") != "rigid":
        L.append(f"> 楼盖假定：用户选择「{d['diaphragm']}」。本版给出**柔性楼盖第一周期** "
                 f"T1,flex={d.get('T1_flex',0):.2f}s 作上界以校核刚性假定对基本周期的敏感性；"
                 "**楼盖平面内柔性引起的内力重分配（真正的弹性楼板）需壳/膜单元，本版未实现**，"
                 "仍按刚性楼盖配筋。狭长/大开洞/楼板不连续工程请用商业软件做弹性楼板专项。")
    L.append("")

    # 六、周期、振型与地震作用
    L.append("## 六、自振周期、振型与地震作用\n")
    L.append("| 振型 | 周期 T(s) | 振型类别 |")
    L.append("|------|----------|----------|")
    for i, (T, kind) in enumerate(d["modes"][:9], 1):
        L.append(f"| {i} | {T:.3f} | {kind} |")
    L.append("")
    L.append(f"第一平动周期 T1={s['Tx']:.3f} s（X）/ {s['Ty']:.3f} s（Y）；第一扭转周期 Tt={s['Tt']:.3f} s。")
    L.append(f"**周期比 Tt/T1 = {s['period_ratio']:.3f}**（GB 50011 3.4.5，限值 0.90）。")
    L.append("")
    L.append(f"基底剪力（CQC 组合）：Vx={s['base_x']/1e3:.0f} kN，Vy={s['base_y']/1e3:.0f} kN，"
             f"双向组合 {s['base_bi']/1e3:.0f} kN。")
    L.append(f"**剪重比 = {s['shear_weight']*100:.2f}%**（GB 50011 5.2.5，{p['seismic_grade']}最小值约 1.6%）。")
    L.append("")

    v = d.get("vertical")
    if v:
        L.append(f"**竖向地震作用**（GB 50011 5.3）：α_v,max=0.65·α_max={v['alpha_vmax']:.3f}，"
                 f"竖向地震标准值 F_Evk={v['Evk']/1e3:.0f} kN（G_eq=0.75ΣG_rep），"
                 f"引起的最大柱轴力增量 ≈ {v['col_N']:.0f} kN，已叠加入柱轴力设计值。")
        L.append("")

    # 六之二、风荷载作用（GB 50009 第8章）
    w = d.get("wind")
    if w:
        L.append("### 6.2 风荷载作用（GB 50009-2012 第8章）\n")
        L.append(f"基本风压 w0={w['w0']} kN/m²，地面粗糙度类别 {w['terrain']}，"
                 f"体型系数 μs={w['mu_s']}，结构高度 H={w['H']:.1f} m。")
        L.append(f"风压沿高度按 wk(z)=βz·μs·μz(z)·w0 计算（μz 按表 8.2.1，"
                 f"{'H>30m 计入风振系数 βz' if w['H']>30 else 'H≤30m 可不计风振 βz=1.0'}）。")
        L.append(f"**风基底剪力：Wx={w['base_x']/1e3:.0f} kN，Wy={w['base_y']/1e3:.0f} kN**；"
                 f"风致最大层间位移角 1/{1/max(w['drift_x'],w['drift_y'],1e-9):.0f}。")
        ctrl = "**风荷载控制**" if w['controls'] else "地震作用控制"
        L.append(f"水平作用由{ctrl}（基底剪力包络取大用于构件设计）。")
        L.append("> 说明：本计算为顺风向等效静力（矩形平面、刚性楼盖）；横风向涡激、扭转风振及"
                 "高柔结构精确顺风向风振须按 GB 50009 8.4/8.5 专项计算，重要工程由商业软件复核。")
        L.append("")

    # 六之三、温度作用（GB 50009 第9章）
    t = d.get("thermal")
    if t:
        L.append("### 6.3 温度作用（GB 50009-2012 第9章）\n")
        L.append(f"均匀温差 ΔT={t['dT']:.0f} ℃，线膨胀系数 α={t['alpha']:.1e} /℃。"
                 f"对楼面梁施加等效热轴力 P=E·A·α·ΔT，由空间杆系求解温度内力。")
        L.append(f"**温度作用引起的最大柱附加弯矩 ≈ {t['col_M']:.0f} kN·m**，"
                 f"已按伴随可变作用（γQ·ψc≈0.9）叠加入柱设计弯矩。")
        L.append("> 说明：取均匀温差、未计混凝土收缩/徐变松弛、**未按伸缩缝释放**"
                 "（设缝可显著降低温度效应）；楼盖按杆系等代。重要工程须专项分析。")
        L.append("")

    # 七、位移验算
    L.append("## 七、水平位移验算\n")
    L.append(f"- **最大层间位移角** = 1/{1/max(d['drift'],1e-9):.0f}（GB 50011 5.5.1，框架-剪力墙限值 1/800）。")
    L.append(f"- **位移比** X={s['disp_ratio_x']:.2f}，Y={s['disp_ratio_y']:.2f}"
             f"（GB 50011 3.4.3，限值 1.2，超 1.5 不应采用）。")
    L.append("")
    if fig.get("curves"):
        L.append(f"![图5　楼层剪力与层间位移角沿高度分布]({fig['curves']})")
        L.append("")

    # 七之二、地下室专项 / 短柱
    bm = d.get("basement")
    if bm:
        L.append("### 7.2 地下室专项（GB 50010/50108）\n")
        L.append(f"外墙计算高度 H={bm['H']:.1f} m，地下水头 {bm['water_height']:.1f} m，外墙厚 {bm['wall_t']:.0f} mm。")
        L.append(f"**外墙竖向受力筋（每米板带）：M={bm['M_design']:.0f} kN·m/m → As={bm['As_req']:.0f} mm²/m**"
                 "（静止土压力 K0·γs·z + 水压力 + 地面活载侧压，简化支承板带）。")
        L.append(f"**整体抗浮 Kf={bm['anti_float_Kf']:.2f}**（要求≥1.05，{'满足' if bm['anti_float_ok'] else '不满足→需压重/抗浮锚杆'}）。")
        L.append("> 多层地下室外墙按贯通全高简化板带（偏保守，忽略中间楼板约束）；底板/抗浮锚杆及"
                 "上下部共同作用须专项。上部结构嵌固于地下室顶板(±0.000)。")
        L.append("")
    scd = d.get("short_col")
    if scd:
        L.append(f"**短柱提示**：检出 {scd['n']} 种截面柱净高/截面高<4（净高≈{scd['Hn']}mm，"
                 "错层/夹层/不等高所致）→ 应全高加密箍筋并按 GB 50011 6.3.7 加强抗剪，防脆性剪切破坏。")
        L.append("")

    # 八、整体稳定
    L.append("## 八、整体稳定与二阶效应\n")
    L.append(d.get("stability_note",
             "竖向荷载下结构整体稳定满足要求；重力在水平位移上引起的 P-Δ 二阶效应"
             "已在分析中按几何刚度计入（GB 50011 3.6.3、JGJ 3-2010 5.4）。"))
    L.append("")

    # 九、构件配筋
    L.append("## 九、构件承载力与配筋\n")
    cols = [m for m in d["members"] if m["kind"] == "柱"]
    walls = [m for m in d["members"] if m["kind"] == "墙"]
    beams = [m for m in d["members"] if m["kind"] == "梁"]

    if cols:
        L.append("### 9.1 框架柱（双向偏心受压，GB 50010 6.2.17）\n")
        L.append("| 编号 | 截面 | N(kN) | Mx(kN·m) | My(kN·m) | 轴压比 | 纵筋 | 配筋率 | 结论 |")
        L.append("|------|------|-------|----------|----------|--------|------|--------|------|")
        for m in cols[:16]:
            L.append(f"| {m['id']} | {m['sec']} | {m['N']:.0f} | {m['Mx']:.0f} | {m['My']:.0f} | "
                     f"{m.get('mu',0):.2f} | {m['bars']} | {m['rho']*100:.2f}% | {'✔' if m['ok'] else '✗'} |")
        L.append("")
        if fig.get("col_section"):
            L.append(f"![图3　代表性框架柱配筋大样]({fig['col_section']})")
            L.append("")
    if walls:
        L.append("### 9.2 剪力墙墙肢（GB 50011 6.4，GB 50010 6.2）\n")
        L.append("| 编号 | 截面 | N(kN) | 面内M(kN·m) | 轴压比 | 竖向分布筋 | 边缘构件 | 结论 |")
        L.append("|------|------|-------|------------|--------|-----------|----------|------|")
        for m in walls[:12]:
            L.append(f"| {m['id']} | {m['sec']} | {m['N']:.0f} | {m['M']:.0f} | {m.get('mu',0):.2f} | "
                     f"{m.get('vdist','—')} | {m['bars']} | {'✔' if m['ok'] else '✗'} |")
        L.append("")
        if fig.get("wall_section"):
            L.append(f"![图4　剪力墙墙肢配筋大样]({fig['wall_section']})")
            L.append("")
    if beams:
        L.append("### 9.3 框架梁（正截面受弯，GB 50010 6.2.10）\n")
        L.append("| 编号 | 主/次 | 截面 | M(kN·m) | 纵筋As(mm²) | 配筋 | 结论 |")
        L.append("|------|-------|------|---------|------------|------|------|")
        for m in beams[:12]:
            kb = m.get("beam_kind", "主")
            L.append(f"| {m['id']} | {'主梁KL' if kb=='主' else '次梁L'} | {m['sec']} | {m['M']:.0f} | "
                     f"{m['As']:.0f} | {m['bars']} | {'✔' if m['ok'] else '✗'} |")
        L.append("")
        if any(m.get("beam_kind") == "次" for m in beams):
            L.append("> 次梁(L)支于主梁，其支座反力已作为集中力计入相应主梁(KL)设计（次梁导算）。")
            L.append("")

    # 十、规范指标汇总
    L.append("## 十、规范控制指标汇总\n")
    L.append("| 控制指标 | 计算值 | 限值 | 结论 |")
    L.append("|----------|--------|------|------|")
    for name, val, lim, ok in d["checks_table"]:
        L.append(f"| {name} | {val} | {lim} | {'✔满足' if ok else '✗超限'} |")
    L.append("")

    # 十一、结论
    L.append("## 十一、结论\n")
    nbad = sum(0 if m["ok"] else 1 for m in d["members"])
    allok = nbad == 0 and all(ok for *_ , ok in d["checks_table"])
    L.append(f"竖向构件 {len(cols)+len(walls)} 个、梁 {len(beams)} 个；其中不满足 {nbad} 个。"
             f"主要规范控制指标{'均满足要求' if allok else '存在超限项（见上表）'}。")
    L.append(f"竖向构件纵筋估算用量约 **{d.get('steel_t',0):.1f} t**。")
    L.append("")
    L.append("> **说明**：本计算书由 structdesign 自动生成，采用三维刚性楼盖模型、"
             "振型分解反应谱+CQC、柱双偏压与墙肢三维内力配筋。计算结果为方案/初步设计深度，"
             "施工图阶段应采用经审定的商业三维分析软件复核，并由具备资质的注册结构工程师"
             "审核、签字并对工程安全负责。")
    L.append("")
    return "\n".join(L)
