"""评估引擎：量化「校园智答」的检索质量和 Agent 判断准确性。

运行：在项目根目录，python eval.py（或 python -m eval）

指标：
  RAG 链路  → 命中率(正确块是否在返回结果里)、MRR(正确答案排第几)
  Agent 链路 → 结论正确率(满足/不满足/不在范围)
"""
import json
import os
import sys

# 让 Python 能 import 项目内模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.rag import get_engine
from app import agent


EVAL_FILE = os.path.join(os.path.dirname(__file__), "data", "eval_set.json")


def load_eval_set():
    with open(EVAL_FILE, encoding="utf-8") as f:
        return json.load(f)


# ================= RAG 评估 =================
def rag_hit(doc: str, expected_block: str) -> bool:
    """判断一条检索结果是否包含期望的制度块标题。"""
    return expected_block in doc


def eval_rag(cases: list[dict]):
    """跑 RAG 检索评估，输出命中率 + MRR。"""
    hits = 0
    rr_sum = 0.0  # 倒数排名之和
    total = len(cases)

    print("=" * 60)
    print("RAG 检索评估")
    print("=" * 60)
    for i, c in enumerate(cases, 1):
        docs = get_engine().search(c["question"], top_k=3)
        hit = any(rag_hit(d, c["expected_block"]) for d in docs)
        # MRR：正确答案在第几位（从 0 开始），没命中记 0
        pos = next((j + 1 for j, d in enumerate(docs) if rag_hit(d, c["expected_block"])), 0)
        rr = 1 / pos if pos else 0
        hits += hit
        rr_sum += rr
        flag = "✅" if hit else "❌"
        print(f"  #{i} {flag} 排名={pos} | {c['question'][:30]}")
        if not hit:
            print(f"       期望块=[{c['expected_block']}]  实际检索={[d[:30]+'...' for d in docs]}")

    hit_rate = hits / total * 100
    mrr = rr_sum / total
    print(f"\n  命中率: {hits}/{total} = {hit_rate:.1f}%")
    print(f"  MRR:    {mrr:.3f}")
    print()
    return hit_rate, mrr


# ================= Agent 评估 =================
def eval_agent(cases: list[dict]):
    """跑 Agent 多轮推理评估，输出结论正确率。"""
    total = len(cases)
    correct = 0
    details = []

    print("=" * 60)
    print("Agent 转专业判断评估")
    print("=" * 60)
    for i, c in enumerate(cases, 1):
        sid = f"eval_sid_{i}"
        answer = ""
        for turn in c["turns"]:
            answer = agent.run(sid, turn)

        # 判断结论方向
        if "不满足" in answer or "不" in answer[:20] and "满足条件" not in answer:
            judged = "不满足"
        elif "不在" in answer[:20] or "限大一" in answer:
            judged = "不在范围"
        elif "满足" in answer[:20]:
            judged = "满足"
        else:
            judged = "未知"

        ok = judged == c["expect"]
        correct += ok
        details.append({"expect": c["expect"], "judged": judged, "ok": ok, "answer": answer[:60]})
        flag = "✅" if ok else "❌"
        print(f"  #{i} {flag} 预期={c['expect']}  判出={judged} | {c['turns']}")

    acc = correct / total * 100
    print(f"\n  正确率: {correct}/{total} = {acc:.1f}%")
    print()
    return acc, details


# ================= 主程序 =================
if __name__ == "__main__":
    data = load_eval_set()
    rag_hit_rate, rag_mrr = eval_rag(data["rag_cases"])
    agent_acc, _ = eval_agent(data["agent_cases"])

    print("=" * 60)
    print("总览")
    print("=" * 60)
    print(f"  RAG 命中率: {rag_hit_rate:.1f}%   MRR: {rag_mrr:.3f}")
    print(f"  Agent 正确率: {agent_acc:.1f}%")
    print()

    # 快速判断面试准备度
    if rag_hit_rate >= 85 and agent_acc >= 80:
        print("✅ 当前质量可上线演示或作为 MVP 交付。")
    elif rag_hit_rate >= 70 or agent_acc >= 60:
        print("⚡ 中等水平，建议优先提升 RAG 检索（混合检索+Rerank）或完善规则库。")
    else:
        print("🔧 基础阶段，先重点排查检索或槽位抽取问题。")