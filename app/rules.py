"""规则引擎：把「转专业」从"念政策原文"升级成"结构化精确判断"。

RAG 只能检索原文；规则引擎能结合学生的年级/GPA/意向专业，按规则算出"能不能转"。
"""
import re

HOT_MAJORS = {"计算机科学与技术", "计算机", "金融学", "金融", "法学"}
ALLOWED_GRADES = ("大一", "大二")
GENERAL_GPA = 3.0   # 普通专业最低绩点
HOT_GPA = 3.5       # 热门专业最低绩点


def route_transfer(text: str):
    """判断这条转专业问题走哪条路：
    'fact'  = 事实问答（条件/政策/流程）→ 走 RAG 检索原文
    'judge' = 个人判断（我想/能不能转）→ 走规则引擎多轮追问+判断
    None    = 与转专业无关
    """
    if not any(k in text for k in ("转专业", "换专业")):
        return None
    if any(k in text for k in ("条件", "政策", "办法", "流程", "规定", "什么时候", "需要什么")):
        return "fact"
    return "judge"


def extract_slots(text: str, slots: dict) -> dict:
    """从用户一句话里提取 年级 / GPA / 意向专业，回填（不覆盖已有值）。"""
    if not slots.get("grade"):
        for g in ("大四", "大三", "大二", "大一"):   # 从长到短匹配，避免"大一"误伤"大二"
            if g in text:
                slots["grade"] = g
                break
    if slots.get("gpa") is None:
        m = re.search(r"(\d(?:\.\d)?)", text)
        if m and re.search(r"(gpa|绩点|平均|绩)", text, re.I):
            slots["gpa"] = float(m.group(1))
    if not slots.get("major"):
        for mj in ("计算机科学与技术", "计算机", "金融学", "金融", "法学", "软件工程", "人工智能", "会计", "英语"):
            if mj in text:
                slots["major"] = mj
                break
    return slots


def missing_slots(slots: dict) -> list[str]:
    """返回还缺哪些信息（用于追问）。"""
    asks = []
    if not slots.get("grade"):
        asks.append("你是大几？")
    if slots.get("gpa") is None:
        asks.append("你上学期的平均绩点（GPA，满分 4.0）是多少？")
    if not slots.get("major"):
        asks.append("你想转入哪个专业？")
    return asks


def judge_transfer(slots: dict) -> str:
    """信息齐全后，按规则给出精确结论。"""
    grade, gpa, major = slots.get("grade"), slots.get("gpa"), slots.get("major")

    if grade not in ALLOWED_GRADES:
        return f"转专业限大一、大二学生申请，你当前是{grade}，不在可申请范围。"

    hot = major in HOT_MAJORS
    threshold = HOT_GPA if hot else GENERAL_GPA
    if gpa < threshold:
        return (
            f"{major} 属于{'热门' if hot else '普通'}专业，要求 GPA 不低于 {threshold}，"
            f"你当前 {gpa} 不满足条件，暂时无法申请。"
        )

    return (
        f"你满足转入 {major} 的基本条件（GPA {gpa} ≥ {threshold}）。"
        f"可在春季学期第 5-8 周向所在学院提交《转专业申请表》，之后参加转入专业组织的考核。"
    )