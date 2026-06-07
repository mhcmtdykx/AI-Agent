"""
辅助工具函数
"""
import os
import logging
from typing import Optional


def load_env_file(filepath: str, override: bool = False) -> dict:
    """
    加载 .env 文件并设置环境变量

    Args:
        filepath: .env 文件路径
        override: 是否覆盖已存在的环境变量

    Returns:
        解析出的键值对字典
    """
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                env_vars[key] = value
                if override or key not in os.environ:
                    os.environ[key] = value
    return env_vars


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    设置日志配置

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为None则只输出到控制台
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = [logging.StreamHandler()]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
        force=True,
    )


def format_message(role: str, content: str) -> dict:
    """
    格式化消息

    Args:
        role: 角色 (user, assistant, system)
        content: 消息内容

    Returns:
        格式化的消息字典
    """
    return {"role": role, "content": content}


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    截断文本

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
