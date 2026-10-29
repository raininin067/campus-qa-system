"""多租户 RAG 引擎：每所学校一个独立的 ChromaDB collection。

- 切换学校 = 切换 collection（数据完全隔离）
- 延迟初始化：不调用 get_engine() 就不占内存
"""
import os
import chromadb
from sentence_transformers import SentenceTransformer

from . import tenant as tnt

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_OFFLINE'] = '1'

# 全局共享（只加载一次，省显存）
_client = chromadb.Client()
_embed_model = SentenceTransformer('BAAI/bge-small-zh-v1.5', local_files_only=True)
_engines: dict[str, 'RAGEngine'] = {}


class RAGEngine:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        col_name = f"kb_{tenant_id}"
        try:
            _client.delete_collection(col_name)
        except Exception:
            pass
        self.collection = _client.create_collection(col_name)

        text = tnt.get_data(tenant_id)
        if not text:
            chunks = ["暂未上传学校制度。"]
        else:
            chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
        print(f"[RAG] 租户 {tenant_id} 切分为 {len(chunks)} 块")

        ids = [f"chunk_{i}" for i in range(len(chunks))]
        embs = _embed_model.encode(chunks, normalize_embeddings=True)
        self.collection.add(documents=chunks, embeddings=embs.tolist(), ids=ids)

    def search(self, query: str, top_k: int = 3):
        qemb = _embed_model.encode([query], normalize_embeddings=True)
        results = self.collection.query(query_embeddings=qemb.tolist(), n_results=top_k)
        if results["documents"] and results["documents"][0]:
            return results["documents"][0]
        return []


def get_engine(tenant_id: str | None = None) -> RAGEngine:
    """获取某个学校的检索引擎（延迟初始化，按需创建）。"""
    tid = tenant_id or tnt.DEFAULT_TENANT
    if tid not in _engines:
        _engines[tid] = RAGEngine(tid)
    return _engines[tid]


def rebuild_engine(tenant_id: str) -> RAGEngine:
    """强制重建（老师改了制度后调用）。"""
    _engines.pop(tenant_id, None)
    return get_engine(tenant_id)


# 保留旧模块调用兼容（llm.py/agent.py 仍 import rag_engine 的地方）
rag_engine = None  # 废弃；所有调用走 get_engine()