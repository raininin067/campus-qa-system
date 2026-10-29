from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import os
from .config import settings
from .llm import generate_stream_response
from . import tenant as tnt
from .rag import get_engine, rebuild_engine

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)


class ChatRequest(BaseModel):
    query: str
    user_id: str = "test_user"


class TenantData(BaseModel):
    tenant_id: str
    name: str = ""
    text: str


# 1. 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}


# 2. 核心流式对话接口
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    return StreamingResponse(
        generate_stream_response(request.user_id, request.query),
        media_type="text/event-stream"
    )


# 3. 管理后台 —— 创建/更新学校制度
@app.post("/admin/tenant")
async def admin_create_tenant(req: TenantData):
    name = req.name or req.tenant_id
    tnt.register(req.tenant_id, name, req.text)
    # 写入文件做持久化
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{req.tenant_id}_school_info.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(req.text)
    # 强制重建检索引擎（让新制度立即生效）
    rebuild_engine(req.tenant_id)
    return {"ok": True, "tenant": req.tenant_id}


# 4. 管理后台 —— 查看所有学校
@app.get("/admin/tenants")
async def admin_list_tenants():
    return tnt.list_tenants()


# 5. 托管网页接口
@app.get("/")
async def read_index():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "找不到 index.html，请确保它在项目根目录下！"}