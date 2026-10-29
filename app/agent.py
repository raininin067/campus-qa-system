"""LangGraph 状态机 + LLM 结构化槽位抽取 ——「校园智答」Agent 编排层。

核心思想（面试要讲的）：
    把一次咨询拆成一张「有状态的图」，节点只做纯计算，会话状态在外部按 session_id 管理。
    - 事实问答（"转专业需要什么条件"）→ 检索节点 → RAG 生成
    - 个人判断（"我想转专业/能不能转"）→ LLM 槽位抽取 → 缺信息就追问 / 全了就规则判断

对比旧版的改进：
    1) 槽位抽取从"正则硬碰"换成"LLM 结构化抽取"，"3.1"、"三点一"、"3.1/4" 都能抽成 3.1
    2) 用 StateGraph 显式建模状态流转，而不是塞在大函数里 if/else
    3) 会话状态按 session_id 隔离（后续可无缝换成 SQLite/Redis 持久化，即 checkpoint）
"""
from typing import TypedDict, Optional
import json
import re

from langgraph.graph import StateGraph, END
from openai import OpenAI

from .rag import get_engine
from .config import settings


# ================= 状态定义 =================
class AgentState(TypedDict):
    question: str           # 本轮用户输入
    intent: str             # "fact" | "judge" | "other"
    grade: Optional[str]    # 槽位：年级
    gpa: Optional[float]    # 槽位：绩点
    major: Optional[str]    # 槽位：意向专业
    answer: str             # 本轮要返回给用户的话


# 会话状态：session_id -> {"grade","gpa","major"}（内存版，后续换持久化）
_sessions: dict[str, dict] = {}

_llm = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)


def _get_session(session_id: str) -> dict:
    return _sessions.setdefault(session_id, {"in_progress": False, "grade": None, "gpa": None, "major": None})


def _clear_session(session_id: str):
    _sessions.pop(session_id, None)


def in_transfer(session_id: str) -> bool:
    """该会话是否正处于「转专业信息追问中」。"""
    return _sessions.get(session_id, {}).get("in_progress", False)


# ================= 意图分流 =================
def classify_intent(text: str) -> str:
    if not any(k in text for k in ("转专业", "换专业")):
        return "other"
    if any(k in text for k in ("条件", "政策", "办法", "流程", "规定", "什么时候", "需要什么")):
        return "fact"
    return "judge"


# ================= LLM 槽位抽取 =================
_SLOT_PROMPT = """你是信息抽取助手。从学生的话里抽取【年级】【绩点GPA】【意向转入专业】三个字段，只输出 JSON 不要解释，字段没有就填 null。格式：{"grade": null, "gpa": null, "major": null}
规则：
- 年级取值："大一"/"大二"/"大三"/"大四"
- gpa 是数字(满分4.0)："3.1"→3.1；"绩点三点一"→3.1；"3.1/4"→3.1
- major 是专业名："计算机"对应"计算机科学与技术"

学生的话：{text}"""


def _parse_json(raw: str) -> dict:
    if not raw:
        return {}
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def _extract_with_llm(text: str) -> dict:
    # 注意：_SLOT_PROMPT 里含有字面花括号 { }，不能用 .format()，改用 replace
    prompt = _SLOT_PROMPT.replace("{text}", text)
    try:
        # 同步调用，避免 FastAPI 异步上下文里 asyncio.run 冲突
        r = _llm.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = r.choices[0].message.content
    except Exception as e:
        print(f"[槽位抽取失败，将用正则兜底] {e}")
        return {}
    return _parse_json(raw)


def _regex_fallback(text: str) -> dict:
    """LLM 抽不到时的正则兜底。"""
    out = {"grade": None, "gpa": None, "major": None}
    for g in ("大四", "大三", "大二", "大一"):
        if g in text:
            out["grade"] = g
            break
    m = re.search(r"(\d(?:\.\d)?)", text)
    if m:
        try:
            out["gpa"] = float(m.group(1))
        except ValueError:
            pass
    for major in ("计算机科学与技术", "计算机", "金融学", "金融", "法学", "软件工程", "人工智能", "会计", "英语", "土木工程", "土木"):
        if major in text:
            out["major"] = major
            break
    return out


def fill_slots(state: AgentState, session_id: str) -> AgentState:
    """抽取本轮槽位，回填到会话状态（只填空缺，不覆盖已有）。"""
    text = state["question"]
    # 出现"转/换专业"即视为一次新判断的起点，清空旧槽位并标记追问开始
    if classify_intent(text) == "judge":
        _sessions[session_id] = {"in_progress": True, "grade": None, "gpa": None, "major": None}
    sess = _get_session(session_id)

    llm_slots = _extract_with_llm(text)
    merged = {}
    merged.update(_regex_fallback(text))     # 正则先兜底
    for k in ("grade", "gpa", "major"):       # LLM 结果优先覆盖
        if llm_slots.get(k):
            merged[k] = llm_slots[k]

    for k in ("grade", "gpa", "major"):
        if sess[k] is None and merged[k] is not None:
            sess[k] = merged[k]

    state["grade"], state["gpa"], state["major"] = sess["grade"], sess["gpa"], sess["major"]
    return state


# ================= 规则判断 =================
HOT_MAJORS = {"计算机科学与技术", "计算机", "金融学", "金融", "法学"}
ALLOWED_GRADES = ("大一", "大二")
GENERAL_GPA = 3.0
HOT_GPA = 3.5


def missing_slots(state: AgentState) -> list[str]:
    asks = []
    if not state.get("grade"):
        asks.append("你是大几？")
    if state.get("gpa") is None:
        asks.append("你上学期的平均绩点（GPA，满分 4.0）是多少？")
    if not state.get("major"):
        asks.append("你想转入哪个专业？")
    return asks


def judge_transfer(state: AgentState) -> str:
    grade, gpa, major = state["grade"], state["gpa"], state["major"]
    if grade not in ALLOWED_GRADES:
        return f"转专业限大一、大二学生申请，你当前是{grade}，不在可申请范围。"
    hot = major in HOT_MAJORS
    threshold = HOT_GPA if hot else GENERAL_GPA
    if gpa < threshold:
        return f"{major} 属于{'热门' if hot else '普通'}专业，要求 GPA 不低于 {threshold}，你当前 {gpa} 不满足条件，暂时无法申请。"
    return f"你满足转入 {major} 的基本条件（GPA {gpa} ≥ {threshold}）。可在春季学期第 5-8 周向所在学院提交《转专业申请表》，之后参加转入专业组织的考核。"


# ================= 图节点（纯计算，不碰 session，靠传入的 session_id） =================
def _node_intent(state: AgentState) -> AgentState:
    state["intent"] = classify_intent(state["question"])
    return state


def _node_rag(state: AgentState) -> AgentState:
    docs = get_engine().search(state["question"], top_k=2)
    state["answer"] = "\n".join(docs) if docs else "暂无相关资料。"
    return state


def _node_judge(session_id: str):
    def _fn(state: AgentState) -> AgentState:
        missing = missing_slots(state)
        if missing:
            state["answer"] = "想帮你准确判断能否转专业，还差几个信息：\n" + "\n".join(f"· {m}" for m in missing)
        else:
            state["answer"] = judge_transfer(state)
            _clear_session(session_id)
        return state
    return _fn


def _node_extract(session_id: str):
    def _fn(state: AgentState) -> AgentState:
        return fill_slots(state, session_id)
    return _fn


# ================= 对外入口：按 session_id 跑一次咨询 =================
def run(session_id: str, question: str) -> str:
    """执行一次咨询，返回最终回复文本。

    路由优先级：
      1) 会话正处于「转专业追问中」→ 继续收集槽位（无论这句话说啥）
      2) 新问题 → 意图分流：judge 走状态机，fact/other 走 RAG
    """
    _get_session(session_id)  # 确保有状态

    # 优先：追问中，续接
    if in_transfer(session_id):
        state = {"question": question, "intent": "judge",
                 "grade": _sessions[session_id]["grade"],
                 "gpa": _sessions[session_id]["gpa"],
                 "major": _sessions[session_id]["major"], "answer": ""}
        fill_slots(state, session_id)
        missing = missing_slots(state)
        if missing:
            return "想帮你准确判断能否转专业，还差几个信息：\n" + "\n".join(f"· {m}" for m in missing)
        answer = judge_transfer(state)
        _clear_session(session_id)
        return answer

    # 新问题：先分流
    intent = classify_intent(question)
    if intent == "judge":
        state = {"question": question, "intent": "judge", "grade": None, "gpa": None, "major": None, "answer": ""}
        fill_slots(state, session_id)
        missing = missing_slots(state)
        if missing:
            return "想帮你准确判断能否转专业，还差几个信息：\n" + "\n".join(f"· {m}" for m in missing)
        answer = judge_transfer(state)
        _clear_session(session_id)
        return answer

    # fact / other → RAG
    docs = get_engine().search(question, top_k=2)
    return "\n".join(docs) if docs else "暂无相关资料。"