
## 五、脚本文件补充

### 1. scripts/clear_cache.sh
```bash
#!/bin/bash
# 清理V6.0系统缓存脚本

BASE_DIR="market_state_system_v6"

echo "🧹 清理V6.0系统缓存..."
echo ""

# 清理cache目录
if [ -d "$BASE_DIR/cache" ]; then
    echo "✅ 清理cache目录..."
    rm -rf "$BASE_DIR/cache"/*
    echo "   已清理cache目录"
fi

# 清理reports目录（保留最近7天）
if [ -d "$BASE_DIR/reports/html" ]; then
    echo "✅ 清理reports目录（保留最近7天）..."
    find "$BASE_DIR/reports/html" -name "*.html" -type f -mtime +7 -delete
    find "$BASE_DIR/reports/png" -name "*.png" -type f -mtime +7 -delete
    echo "   已清理reports目录"
fi

# 清理logs目录（保留最近30天）
if [ -d "$BASE_DIR/logs" ]; then
    echo "✅ 清理logs目录（保留最近30天）..."
    find "$BASE_DIR/logs" -name "*.log" -type f -mtime +30 -delete
    echo "   已清理logs目录"
fi

# 清理__pycache__目录
echo "✅ 清理__pycache__目录..."
find "$BASE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "   已清理__pycache__目录"

echo ""
echo "✅ 缓存清理完成！"
echo ""
echo "📊 磁盘空间释放统计:"
du -sh "$BASE_DIR/cache" 2>/dev/null || echo "   cache目录已清空"
du -sh "$BASE_DIR/reports" 2>/dev/null || echo "   reports目录已清理"
du -sh "$BASE_DIR/logs" 2>/dev/null || echo "   logs目录已清理"