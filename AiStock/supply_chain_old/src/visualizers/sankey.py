import plotly.graph_objects as go
from typing import Dict, Any
from .base import BaseVisualizer

class SankeyVisualizer(BaseVisualizer):
    def render(self, chain_data: Dict[str, Any]) -> go.Figure:
        nodes, links = self._build_nodes_links(chain_data)
        colors = self.theme.get("colors", {})
        
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=self.theme.get("sankey_node_pad", 15),
                thickness=self.theme.get("sankey_node_thickness", 20),
                line=dict(color="black", width=0.5),
                label=nodes["labels"],
                color=nodes["colors"],
                customdata=nodes["values"],
                hovertemplate="<b>%{label}</b><br>权重: %{customdata}<extra></extra>"
            ),
            link=dict(
                source=links["src"],
                target=links["tgt"],
                value=links["val"],
                color=[colors.get("primary", "#2563eb")] * len(links["src"]),
                hovertemplate="流向: %{label}<br>流量: %{value}<extra></extra>"
            )
        )])
        return self._apply_layout(fig, f"<b>{chain_data['name']}</b> 产业链上下游流向")

    def _build_nodes_links(self, data: Dict[str, Any]) -> tuple:
        labels, colors, values, idx_map = [], [], [], {}
        src, tgt, val, labels_link = [], [], [], []
        curr = 0
        
        for layer in data.get("layers", []):
            for node in layer.get("nodes", []):
                name = node["name"].replace("\n", " ")
                labels.append(name)
                colors.append(node.get("color", "#888888"))
                values.append(node.get("value", 50))
                idx_map[f"{layer['name']}_{name}"] = curr
                curr += 1
                
        for link in data.get("links", []):
            s_layer = next((l for l in data["layers"] if l["name"] == link["source"]), None)
            t_layer = next((l for l in data["layers"] if l["name"] == link["target"]), None)
            if not s_layer or not t_layer: continue
            
            for sn in s_layer["nodes"][:2]:
                for tn in t_layer["nodes"][:2]:
                    s_key = f"{link['source']}_{sn['name'].replace('\n', ' ')}"
                    t_key = f"{link['target']}_{tn['name'].replace('\n', ' ')}"
                    if s_key in idx_map and t_key in idx_map:
                        src.append(idx_map[s_key])
                        tgt.append(idx_map[t_key])
                        val.append(link["value"])
                        labels_link.append(f"{link['source']} → {link['target']}")
                        
        return {"labels": labels, "colors": colors, "values": values}, {"src": src, "tgt": tgt, "val": val}