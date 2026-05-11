# supply_chain/src/builder.py
from typing import Dict, List, Any

class GraphDataBuilder:
    """关系图构建器：将 YAML 拓扑映射为 Plotly 渲染结构，自动处理标的关系着色"""
    
    # 关系类型 -> 链路颜色映射
    RELATION_COLORS = {
        "macro": "rgba(180,180,180,0.20)",
        "belong": "rgba(69,123,157,0.35)",
        "supply": "rgba(42,157,143,0.60)",
        "compete": "rgba(230,57,70,0.50)",
        "cooperate": "rgba(233,196,106,0.55)"
    }

    @staticmethod
    def build(config: Dict[str, Any]) -> Dict[str, Any]:
        nodes = config["nodes"]
        links = config["links"]
        
        # 1. 节点索引映射
        id_map = {n["id"]: idx for idx, n in enumerate(nodes)}
        labels = [n["name"] for n in nodes]
        colors = [n.get("color", "#888888") for n in nodes]
        
        # 2. 链路数据转换
        src_list, tgt_list, val_list, col_list, hover_list = [], [], [], [], []
        
        for link in links:
            s_idx = id_map.get(link["source"])
            t_idx = id_map.get(link["target"])
            if s_idx is None or t_idx is None:
                continue  # 跳过无效引用
                
            rel_type = link.get("type", "belong")
            desc = link.get("desc", "")
            
            src_list.append(s_idx)
            tgt_list.append(t_idx)
            val_list.append(link.get("value", 10))
            col_list.append(GraphDataBuilder.RELATION_COLORS.get(rel_type, "rgba(100,100,100,0.3)"))
            hover_list.append(
                f"<b>{labels[s_idx]}</b> → <b>{labels[t_idx]}</b><br>"
                f"关系类型: {rel_type.upper()}<br>{desc}<br>关联权重: {link.get('value', '')}"
            )
            
        return {
            "nodes": {"label": labels, "color": colors},
            "links": {
                "source": src_list, "target": tgt_list,
                "value": val_list, "color": col_list, "hover": hover_list
            }
        }