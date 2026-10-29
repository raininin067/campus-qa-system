from openai import AsyncOpenAI
from .config import settings
from .rag import get_engine
from . import agent


client = AsyncOpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY
)


async def generate_stream_response(user_id: str, prompt: str):
    # ── agent 流程 ──
    if agent.in_transfer(user_id):
        reply = agent.run(user_id, prompt)
        yield reply
        return

    intent = agent.classify_intent(prompt)
    if intent == "judge":
        reply = agent.run(user_id, prompt)
        yield reply
        return

    # ── 同时搜 RAG + 联网 ──
    from .search import web_search
    import asyncio

    engine = get_engine(user_id)

    # RAG 检索
    retrieved_docs = engine.search(prompt, top_k=2)
    print(f"🔍 [RAG] 问题: {prompt}")
    print(f"🔍 [RAG结果]: {[d[:50]+'...' for d in retrieved_docs]}")

    # 联网搜索（始终搜，RAG 有结果也搜）
    web_docs = web_search(prompt, max_results=4)
    print(f"🔍 [联网]: {[d[:50]+'...' for d in web_docs]}" if web_docs else "🔍 [联网] 无结果")

    # ── 拼接上下文 ──
    parts = []

    if retrieved_docs:
        parts.append("=== 校内资料 ===\n" + "\n\n".join(retrieved_docs))

    if web_docs:
        parts.append(
            "=== 互联网搜索结果 ===\n"
            + "\n\n".join(f"[结果{i+1}] {d}" for i, d in enumerate(web_docs))
        )

    context = "\n\n\n".join(parts) if parts else "无任何资料"

    # ── 极简 prompt ──
    system_prompt = f"""你是一个校园招生咨询助手。你必须根据参考资料回答学生问题。
核心规则：
- 学生问的是【外校/其他大学/外部信息】→ 只看"=== 互联网搜索结果 ==="，不能用校内资料
- 学生问的是【本校/我们学校/校内制度】→ 优先看"=== 校内资料 ==="
- 不确定时，优先用互联网搜索结果的回答
- 回答末尾加"（信息来自互联网，仅供参考）"

【参考资料】：
{context}"""

    try:
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            stream=True
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        print(f"[大模型调用失败] {e}")
        yield "抱歉，系统繁忙，请稍后再试。"