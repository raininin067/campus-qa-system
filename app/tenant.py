"""多租户管理：每所学校一套知识库隔离。

已从内存版升级为 MySQL 持久化，重启服务数据不丢失。
"""
import os
from .db import get_connection

DEFAULT_TENANT = "default"


def register(tenant_id: str, name: str, text: str):
    """注册/更新一所学校的数据（写入 MySQL）。"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tenants (id, name, data) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE name=%s, data=%s",
            (tenant_id, name, text, name, text),
        )
        conn.commit()


def get_data(tenant_id: str) -> str:
    """返回该学校的知识库原文；不存在则回退到默认。"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM tenants WHERE id=%s", (tenant_id,))
        row = cursor.fetchone()
        if row:
            return row["data"]
        cursor.execute("SELECT data FROM tenants WHERE id=%s", (DEFAULT_TENANT,))
        row = cursor.fetchone()
        return row["data"] if row else ""


def list_tenants():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM tenants ORDER BY created_at")
        return [{"id": r["id"], "name": r["name"]} for r in cursor.fetchall()]


def exists(tenant_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tenants WHERE id=%s", (tenant_id,))
        return cursor.fetchone() is not None


# ── 启动时把 data/school_info.txt 注册为默认学校 ──
_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_default_file = os.path.join(_data_dir, "school_info.txt")

if os.path.exists(_default_file):
    with open(_default_file, encoding="utf-8") as f:
        text = f.read()
    register(DEFAULT_TENANT, "默认高校", text)