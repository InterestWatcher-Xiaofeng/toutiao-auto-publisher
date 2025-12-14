"""
日志系统
"""

import os
import sys
from datetime import datetime
from loguru import logger

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'logs')


def setup_logger():
    """配置日志系统"""
    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG"
    )
    
    # 添加文件输出
    log_file = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="00:00",  # 每天轮转
        retention="30 days",  # 保留30天
        encoding="utf-8"
    )
    
    logger.info("日志系统初始化完成")
    return logger


def get_logger():
    """获取日志实例"""
    return logger

