"""MySQL 数据库连接封装。"""
import pymysql
from .config import settings


def get_connection():
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_db():
    """首次运行建表。"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 学校/租户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id          VARCHAR(64) PRIMARY KEY  COMMENT '学校ID',
                name        VARCHAR(128) NOT NULL    COMMENT '学校名称',
                data        TEXT NOT NULL            COMMENT '制度原文',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学校知识库';
        """)

        # 问答记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_records (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                tenant_id   VARCHAR(64) NOT NULL     COMMENT '学校ID',
                question    TEXT NOT NULL            COMMENT '用户问题',
                answer      TEXT NOT NULL            COMMENT '系统回答',
                model       VARCHAR(64) DEFAULT ''   COMMENT '使用的模型',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_tenant (tenant_id),
                INDEX idx_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问答记录';
        """)

        # 评估结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eval_results (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                eval_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
                rag_hit_rate FLOAT COMMENT 'RAG命中率',
                rag_mrr     FLOAT COMMENT 'MRR',
                agent_acc   FLOAT COMMENT 'Agent准确率',
                details     JSON COMMENT '详细结果'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评估记录';
        """)

        conn.commit()
        print("数据库表初始化完成")