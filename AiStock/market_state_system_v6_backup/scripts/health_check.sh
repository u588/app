#!/bin/bash
# V6.0系统健康检查脚本

BASE_DIR="market_state_system_v6"
LOG_FILE="$BASE_DIR/logs/health_check_$(date +%Y%m%d_%H%M%S).log"

echo "🏥 V6.0系统健康检查" | tee "$LOG_FILE"
echo "====================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 检查1：目录结构
echo "1️⃣ 检查目录结构..." | tee -a "$LOG_FILE"
REQUIRED_DIRS=(
    "config"
    "services/core_services"
    "services/supplementary_services"
    "services/visualization_service"
    "infrastructure/communication_layer"
    "infrastructure/base_services"
    "infrastructure/data_service"
    "main_system"
    "utils"
    "notebooks"
    "reports"
    "logs"
    "cache"
)

MISSING_DIRS=()
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$BASE_DIR/$dir" ]; then
        MISSING_DIRS+=("$dir")
        echo "   ❌ 缺失目录: $dir" | tee -a "$LOG_FILE"
    fi
done

if [ ${#MISSING_DIRS[@]} -eq 0 ]; then
    echo "   ✅ 所有必需目录存在" | tee -a "$LOG_FILE"
else
    echo "   ⚠️ 缺失 ${#MISSING_DIRS[@]} 个目录" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 检查2：配置文件
echo "2️⃣ 检查配置文件..." | tee -a "$LOG_FILE"
REQUIRED_CONFIGS=(
    "system_config_v6.yaml"
    "index_name_mapping.yaml"
    "logging_config.yaml"
    "visualization_config.yaml"
)

MISSING_CONFIGS=()
for config in "${REQUIRED_CONFIGS[@]}"; do
    if [ ! -f "$BASE_DIR/config/$config" ]; then
        MISSING_CONFIGS+=("$config")
        echo "   ❌ 缺失配置: $config" | tee -a "$LOG_FILE"
    fi
done

if [ ${#MISSING_CONFIGS[@]} -eq 0 ]; then
    echo "   ✅ 所有必需配置存在" | tee -a "$LOG_FILE"
else
    echo "   ⚠️ 缺失 ${#MISSING_CONFIGS[@]} 个配置文件" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 检查3：Python环境
echo "3️⃣ 检查Python环境..." | tee -a "$LOG_FILE"
REQUIRED_PACKAGES=(
    "pandas"
    "numpy"
    "pyyaml"
    "plotly"
    "sqlalchemy"
)

MISSING_PACKAGES=()
for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! python -c "import $package" 2>/dev/null; then
        MISSING_PACKAGES+=("$package")
        echo "   ❌ 缺失包: $package" | tee -a "$LOG_FILE"
    fi
done

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo "   ✅ 所有必需包已安装" | tee -a "$LOG_FILE"
else
    echo "   ⚠️ 缺失 ${#MISSING_PACKAGES[@]} 个Python包" | tee -a "$LOG_FILE"
    echo "   💡 运行: pip install -r requirements/base.txt" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 检查4：服务文件
echo "4️⃣ 检查服务文件..." | tee -a "$LOG_FILE"
REQUIRED_SERVICES=(
    "market_state_service.py"
    "risk_assessment_service.py"
    "allocation_service.py"
    "sentiment_analysis_service.py"
    "commodity_engine_service.py"
    "macro_analysis_service.py"
    "option_pcr_service.py"
    "cross_market_service.py"
    "industry_rotation_service.py"
    "futures_analysis_service.py"
    "visualization_service.py"
)

MISSING_SERVICES=()
for service in "${REQUIRED_SERVICES[@]}"; do
    SERVICE_PATH=""
    if [[ "$service" == *"visualization"* ]]; then
        SERVICE_PATH="$BASE_DIR/services/visualization_service/$service"
    elif [[ "$service" == *"cross_market"* || "$service" == *"industry_rotation"* || "$service" == *"futures_analysis"* ]]; then
        SERVICE_PATH="$BASE_DIR/services/supplementary_services/$service"
    else
        SERVICE_PATH="$BASE_DIR/services/core_services/$service"
    fi
    
    if [ ! -f "$SERVICE_PATH" ]; then
        MISSING_SERVICES+=("$service")
        echo "   ❌ 缺失服务: $service" | tee -a "$LOG_FILE"
    fi
done

if [ ${#MISSING_SERVICES[@]} -eq 0 ]; then
    echo "   ✅ 所有必需服务文件存在" | tee -a "$LOG_FILE"
else
    echo "   ⚠️ 缺失 ${#MISSING_SERVICES[@]} 个服务文件" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 检查5：主系统文件
echo "5️⃣ 检查主系统文件..." | tee -a "$LOG_FILE"
if [ -f "$BASE_DIR/main_system/market_state_system_v6.py" ]; then
    echo "   ✅ 主系统文件存在" | tee -a "$LOG_FILE"
else
    echo "   ❌ 缺失主系统文件" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 检查6：工具文件
echo "6️⃣ 检查工具文件..." | tee -a "$LOG_FILE"
REQUIRED_UTILS=(
    "data_context_preparation.py"
    "validation_utils.py"
    "type_conversion_utils.py"
)

MISSING_UTILS=()
for util in "${REQUIRED_UTILS[@]}"; do
    if [ ! -f "$BASE_DIR/utils/$util" ]; then
        MISSING_UTILS+=("$util")
        echo "   ❌ 缺失工具: $util" | tee -a "$LOG_FILE"
    fi
done

if [ ${#MISSING_UTILS[@]} -eq 0 ]; then
    echo "   ✅ 所有必需工具文件存在" | tee -a "$LOG_FILE"
else
    echo "   ⚠️ 缺失 ${#MISSING_UTILS[@]} 个工具文件" | tee -a "$LOG_FILE"
fi
echo "" | tee -a "$LOG_FILE"

# 生成总结
echo "====================" | tee -a "$LOG_FILE"
echo "📊 健康检查总结" | tee -a "$LOG_FILE"
echo "====================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

TOTAL_CHECKS=6
PASSED_CHECKS=0

[ ${#MISSING_DIRS[@]} -eq 0 ] && ((PASSED_CHECKS++))
[ ${#MISSING_CONFIGS[@]} -eq 0 ] && ((PASSED_CHECKS++))
[ ${#MISSING_PACKAGES[@]} -eq 0 ] && ((PASSED_CHECKS++))
[ ${#MISSING_SERVICES[@]} -eq 0 ] && ((PASSED_CHECKS++))
[ -f "$BASE_DIR/main_system/market_state_system_v6.py" ] && ((PASSED_CHECKS++))
[ ${#MISSING_UTILS[@]} -eq 0 ] && ((PASSED_CHECKS++))

echo "✅ 通过: $PASSED_CHECKS/$TOTAL_CHECKS" | tee -a "$LOG_FILE"

if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "🎉 系统健康检查全部通过！" | tee -a "$LOG_FILE"
    echo "🚀 系统可以正常运行" | tee -a "$LOG_FILE"
    exit 0
else
    echo "" | tee -a "$LOG_FILE"
    echo "⚠️ 系统存在 $((TOTAL_CHECKS - PASSED_CHECKS)) 个问题" | tee -a "$LOG_FILE"
    echo "🔧 请根据上述提示修复问题" | tee -a "$LOG_FILE"
    exit 1
fi