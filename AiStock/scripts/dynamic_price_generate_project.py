# generate_project.py - 一键生成项目结构
import os
from pathlib import Path

def create_project_structure():
    """自动生成项目目录结构"""
    base = Path("AiStock")
    
    # 创建目录
    dirs = [
        "config/dynamic_price",
        "base_services",
        "dynamic_price_system/config",
        "dynamic_price_system/core",
        "dynamic_price_system/data",
        "dynamic_price_system/portfolio",
        "dynamic_price_system/utils",
        "scripts",
        "tests/unit",
        "tests/integration",
        "tests/fixtures",
        "logs/dynamic_price",
        "data/cache",
        "output/dynamic_price",
    ]
    
    for d in dirs:
        (base / d).mkdir(parents=True, exist_ok=True)
    
    print(f"✅ 项目结构创建完成：{base.resolve()}")

if __name__ == "__main__":
    create_project_structure()