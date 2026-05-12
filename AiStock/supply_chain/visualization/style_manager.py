"""
样式管理模块
管理pyvis网络图的所有视觉样式配置
"""

from typing import Dict, Optional


class StyleManager:
    """样式管理器，根据YAML配置生成pyvis节点/边样式"""

    def __init__(self, viz_config: Dict):
        """
        初始化样式管理器

        Args:
            viz_config: 可视化YAML配置
        """
        self.config = viz_config
        self._industry_colors = viz_config.get('industry_colors', {})
        self._chain_level = viz_config.get('chain_level', {})
        self._market_cap_size = viz_config.get('market_cap_size', {})
        self._relationship_styles = viz_config.get('relationship_styles', {})
        self._global = viz_config.get('global', {})
        self._physics = viz_config.get('physics', {})

    def get_node_style(
        self,
        industry: str,
        chain_level: str,
        market_cap: str,
        target_name: str,
        code: str,
        description: str,
        policy_score: int,
        certainty_score: int,
    ) -> Dict:
        """
        生成节点样式

        Args:
            industry: 一级方向
            chain_level: 产业链层级(upstream/midstream/downstream)
            market_cap: 市值规模(大/中/小)
            target_name: 标的名称
            code: 股票代码
            description: 入选说明
            policy_score: 政策契合度
            certainty_score: 投资确定性

        Returns:
            pyvis节点样式字典
        """
        # 行业颜色
        colors = self._industry_colors.get(industry, {
            'primary': '#888888',
            'secondary': '#AAAAAA',
            'background': '#333333',
            'border': '#888888',
            'highlight': '#CCCCCC',
        })

        # 层级形状
        level_config = self._chain_level.get(chain_level, {
            'shape': 'dot',
            'badge': '',
            'badge_color': '#888888',
        })

        # 市值规模
        size_config = self._market_cap_size.get(market_cap, {
            'node_size': 15,
            'border_width': 1,
            'font_size': 10,
            'shadow': False,
        })

        # 构建悬停提示
        level_label = {'upstream': '上游', 'midstream': '中游', 'downstream': '下游'}
        badge = level_config.get('badge', level_label.get(chain_level, ''))

        tooltip = (
            f"<b>{target_name}</b> ({code})<br>"
            f"<hr style='margin:3px 0;border-color:{colors['primary']}'>"
            f"<b>行业</b>: {industry}<br>"
            f"<b>产业链</b>: {badge}<br>"
            f"<b>市值规模</b>: {market_cap}<br>"
            f"<b>政策契合度</b>: {'★' * policy_score}{'☆' * (5 - policy_score)}<br>"
            f"<b>投资确定性</b>: {'★' * certainty_score}{'☆' * (5 - certainty_score)}<br>"
            f"<hr style='margin:3px 0;border-color:{colors['primary']}'>"
            f"<b>说明</b>: {description}"
        )

        node_size = size_config.get('node_size', 15)

        # 根据政策契合度和投资确定性微调大小
        score_bonus = (policy_score + certainty_score) * 1.5
        final_size = node_size + score_bonus

        return {
            'color': {
                'background': colors['background'],
                'border': colors['border'],
                'highlight': {
                    'background': colors['primary'],
                    'border': colors['highlight'],
                },
                'hover': {
                    'background': colors['secondary'],
                    'border': colors['border'],
                },
            },
            'size': final_size,
            'shape': level_config.get('shape', 'dot'),
            'borderWidth': size_config.get('border_width', 2),
            'shadow': {'enabled': size_config.get('shadow', False), 'color': colors['primary']},
            'font': {
                'size': size_config.get('font_size', 12),
                'color': '#E0E0E0',
                'face': self._global.get('font_family', 'sans-serif'),
                'strokeWidth': 3,
                'strokeColor': '#0a0e27',
            },
            'title': tooltip,
            'label': target_name,
        }

    def get_edge_style(self, relation_type: str) -> Dict:
        """
        生成边样式

        Args:
            relation_type: 关系类型(supply_chain/competition/collaboration/verification)

        Returns:
            pyvis边样式字典
        """
        style = self._relationship_styles.get(relation_type, {})
        color = style.get('color', '#888888')
        width = style.get('width', 2)
        dashes = style.get('dashes', False)
        smooth = style.get('smooth', {})
        arrows = style.get('arrows', {})
        label_font = style.get('label_font', {})

        edge_style = {
            'color': {
                'color': color,
                'highlight': color,
                'hover': color,
                'opacity': 0.7,
            },
            'width': width,
            'dashes': dashes,
            'smooth': smooth if smooth else {'type': 'continuous'},
            'hoverWidth': style.get('hover_width', width + 2),
            'selectionWidth': style.get('selection_width', width + 2),
            'font': {
                'size': label_font.get('size', 10),
                'color': label_font.get('color', color),
                'strokeWidth': label_font.get('strokeWidth', 3),
                'strokeColor': label_font.get('strokeColor', '#0a0e27'),
                'face': self._global.get('font_family', 'sans-serif'),
                'align': 'middle',
            },
        }

        if arrows:
            edge_style['arrows'] = arrows

        return edge_style

    def get_industry_color(self, industry: str) -> Dict:
        """获取行业颜色方案"""
        return self._industry_colors.get(industry, {
            'primary': '#888888',
            'secondary': '#AAAAAA',
            'background': '#333333',
            'border': '#888888',
            'highlight': '#CCCCCC',
        })

    def get_physics_config(self) -> Dict:
        """获取物理引擎配置"""
        return self._physics

    def get_interaction_config(self) -> Dict:
        """获取交互配置"""
        return self.config.get('interaction', {})

    def get_legend_config(self) -> Dict:
        """获取图例配置"""
        return self.config.get('legend', {})

    def get_chain_level_badge(self, level: str) -> str:
        """获取产业链层级徽标"""
        level_config = self._chain_level.get(level, {})
        labels = {'upstream': '上游', 'midstream': '中游', 'downstream': '下游'}
        return level_config.get('badge', labels.get(level, ''))

    def get_global_config(self) -> Dict:
        """获取全局配置"""
        return self._global