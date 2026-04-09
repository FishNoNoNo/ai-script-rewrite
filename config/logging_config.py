# config/logging_config.py
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
import os


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """配置结构化日志（按天轮转）"""
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # 每日轮转的主日志文件（每天午夜分割）
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        when="midnight",  # 在每天午夜（00:00）分割
        interval=1,  # 每 1 天分割一次
        backupCount=30,  # 保留最近 30 天的日志
        encoding="utf-8",
        utc=False,  # 使用本地时间（非 UTC）
    )
    file_handler.setFormatter(formatter)
    file_handler.suffix = "%Y-%m-%d"  # 日志文件后缀格式：app.log.2026-02-13

    # 错误日志（也按天分割）
    error_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "error.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.suffix = "%Y-%m-%d"

    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)

    return root_logger
