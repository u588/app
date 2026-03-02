#!/bin/bash
# 初始化V6.0项目目录结构

BASE_DIR="market_state_system_v6"
mkdir -p $BASE_DIR/{config,services/core_services,services/supplementary_services,services/visualization_service/chart_generators,services/visualization_service/templates,infrastructure/communication_layer,infrastructure/base_services,infrastructure/data_service,main_system,utils,reports/{html,png,csv,archive},logs/{archive},cache/{index_data,derivative_data,macro_data},notebooks,tests/{unit_tests,integration_tests,test_data},docs/{architecture,api,user_guide,deployment},scripts,requirements}

# 创建.gitignore
cat > $BASE_DIR/.gitignore << EOF
# 自动生成目录
cache/
logs/
reports/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.ipynb_checkpoints

# 环境变量
.env

# 编辑器
.vscode/
.idea/
*.swp
*.swo
EOF

echo "✅ V6.0项目目录结构初始化完成"
echo "📁 项目路径: $BASE_DIR"
echo "📝 下一步："
echo "   1. 复制配置文件到 config/"
echo "   2. 运行: cd $BASE_DIR && pip install -r requirements/base.txt"
echo "   3. 启动Jupyter: jupyter notebook notebooks/"