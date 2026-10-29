import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 项目基础信息
    PROJECT_NAME: str = "校园智答 - 高校智能咨询系统"
    VERSION: str = "1.0.0"

    # 大模型配置 (因为你要用本地 Ollama，所以这里默认写本地的)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "ollama")  # 本地模型随便填
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:7b")
    # MySQL 数据库配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "campus_qa")

    class Config:
        env_file = ".env"  # 以后可以通过 .env 文件覆盖配置


settings = Settings()