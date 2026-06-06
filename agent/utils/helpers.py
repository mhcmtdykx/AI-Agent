"""
辅助工具函数
"""
import logging
from typing import Optional


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
