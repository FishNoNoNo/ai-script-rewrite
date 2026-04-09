from pathlib import Path


def get_project_path():
    """获取各种项目路径"""

    # 1. 当前工作目录（运行脚本的目录）
    cwd = Path.cwd()
    return cwd
