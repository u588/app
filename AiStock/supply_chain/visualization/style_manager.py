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
        score: float = 0.0,
        target_priority: int = 0,
        config_advice: str = '',
        invest_style: str = '',
        core_ratio: int = 0,
        category: str = '',
        track: str = '',
        track_priority: str = '',
        policy_cycle: str = '',
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
            score: 综合评分
            target_priority: 标的优先级
            config_advice: 配置建议
            invest_style: 投资风格
            core_ratio: 核心业务占比
            category: 二级分类
            track: 三级赛道
            track_priority: 赛道优先级
            policy_cycle: 政策周期

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

        # 优先级标签
        priority_map = {5: 'S5-核心', 4: 'S4-重点', 3: 'S3-适度', 2: 'S2-关注', 1: 'S1-观察'}
        priority_label = priority_map.get(target_priority, '')

        # 配置建议颜色
        advice_colors = {
            '核心配置·长期持有': '#FF6B6B',
            '重点配置·关注回调': '#FFD93D',
            '适度配置·波段操作': '#4ECDC4',
        }
        advice_color = '#E0E0E0'
        for key, val in advice_colors.items():
            if key in config_advice:
                advice_color = val
                break

        tooltip = (
            f"<b style='font-size:15px'>{target_name}</b> <span style='color:#888'>({code})</span><br>"
            f"<hr style='margin:4px 0;border-color:{colors['primary']}'>"
            f"<b>行业</b>: <span style='color:{colors['primary']}'>{industry}</span>"
            f" | <b>层级</b>: <span style='color:{level_config.get('badge_color', '#FF9800')}'>{badge}</span><br>"
        )
        if category:
            tooltip += f"<b>分类</b>: {category}"
            if track:
                tooltip += f" → {track}"
            tooltip += "<br>"
        if track_priority:
            tooltip += f"<b>赛道优先级</b>: {track_priority}<br>"
        if policy_cycle:
            tooltip += f"<b>政策周期</b>: {policy_cycle}<br>"
        tooltip += (
            f"<hr style='margin:4px 0;border-color:rgba(255,255,255,0.1)'>"
            f"<b>市值</b>: {market_cap}盘 | <b>风格</b>: {invest_style}<br>"
            f"<b>政策契合</b>: {'★' * policy_score}{'☆' * (5 - policy_score)} "
            f"<b>确定性</b>: {'★' * certainty_score}{'☆' * (5 - certainty_score)}<br>"
            f"<b>核心占比</b>: {core_ratio}% | <b>综合评分</b>: {score} | <b>优先级</b>: {priority_label}<br>"
            f"<hr style='margin:4px 0;border-color:rgba(255,255,255,0.1)'>"
            f"<b style='color:{advice_color}'>{config_advice}</b><br>"
        )
        if description:
            # 截取说明前80字
            desc_short = description[:80] + ('...' if len(description) > 80 else '')
            tooltip += f"<span style='color:#999;font-size:12px'>{desc_short}</span>"

        node_size = size_config.get('node_size', 15)

        # 根据综合评分微调大小
        score_bonus = score * 3
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
