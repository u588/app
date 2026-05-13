"""
负责网络图的最终渲染、HTML注入（图例/统计等）和文件输出
"""

import os
import re
from typing import Dict, List, Optional
from pyvis.network import Network


class Renderer:
    """渲染器，处理HTML输出和定制化注入"""

    def __init__(self, output_dir: str, viz_config: Dict):
        """
        初始化渲染器

        Args:
            output_dir: 输出目录
            viz_config: 可视化配置
        """
        self.output_dir = output_dir
        self.viz_config = viz_config
        os.makedirs(output_dir, exist_ok=True)

    def render(
        self,
        net: Network,
        filename: str,
        title: str = "产业链关系网络",
        legend_items: Optional[Dict] = None,
        statistics: Optional[Dict] = None,
    ) -> str:
        """
        渲染网络图并保存HTML

        Args:
            net: pyvis Network对象
            filename: 输出文件名
            title: 页面标题
            legend_items: 图例项
            statistics: 统计信息

        Returns:
            输出文件路径
        """
        filepath = os.path.join(self.output_dir, filename)

        # 先让pyvis生成HTML
        net.save_graph(filepath)

        # 注入自定义内容
        self._inject_custom_html(filepath, title, legend_items, statistics)

        print(f"[Renderer] 已输出: {filepath}")
        return filepath

    def _inject_custom_html(
        self,
        filepath: str,
        title: str,
        legend_items: Optional[Dict],
        statistics: Optional[Dict],
    ):
        """注入自定义HTML（标题栏、图例、统计面板等）"""
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入标题栏
        title_bar = self._build_title_bar(title)
        html = html.replace('<body>', f'<body>\n{title_bar}')

        # 注入图例
        if legend_items:
            legend_html = self._build_legend(legend_items)
            html = html.replace('</body>', f'{legend_html}\n</body>')

        # 注入统计面板
        if statistics:
            stats_html = self._build_statistics_panel(statistics)
            html = html.replace('</body>', f'{stats_html}\n</body>')

        # 注入自定义CSS
        custom_css = self._build_custom_css()
        html = html.replace('</head>', f'{custom_css}\n</head>')

        # 注入筛选控件
        filter_html = self._build_filter_controls()
        html = html.replace('</body>', f'{filter_html}\n</body>')

        # ★ 核心修复：注入JS修补vis-network的tooltip渲染
        # vis-network 9.x 使用 innerText 渲染tooltip，导致HTML标签显示为源代码
        # 修补为 innerHTML，使tooltip支持富文本
        tooltip_patch = self._build_tooltip_patch()
        html = html.replace('</body>', f'{tooltip_patch}\n</body>')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

    def _build_title_bar(self, title: str) -> str:
        """构建标题栏HTML"""
        return f'''
        <div id="title-bar" style="
            position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
            background: linear-gradient(135deg, #0a0e27 0%, #1a1e3e 100%);
            border-bottom: 2px solid rgba(78,205,196,0.3);
            padding: 12px 25px;
            display: flex; align-items: center; justify-content: space-between;
            box-shadow: 0 2px 20px rgba(0,0,0,0.5);
        ">
            <div style="display:flex;align-items:center;gap:15px;">
                <div style="
                    width:8px;height:30px;border-radius:4px;
                    background:linear-gradient(180deg,#4ECDC4,#FF6B6B);
                "></div>
                <span style="
                    font-size:20px;font-weight:bold;color:#E0E0E0;
                    font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;
                ">{title}</span>
            </div>
            <div style="font-size:12px;color:#666;">
                产业链分析系统 | 数据驱动投资决策
            </div>
        </div>
        '''

    def _build_legend(self, legend_items: Dict) -> str:
        """构建图例HTML"""
        legend_config = self.viz_config.get('legend', {})

        # 关系类型图例
        relation_legends = ""
        relation_info = {
            'supply_chain': {'label': '供应链关系', 'color': '#4CAF50', 'style': 'solid', 'arrow': True},
            'competition': {'label': '竞争关系', 'color': '#F44336', 'style': 'dashed', 'arrow': False},
            'collaboration': {'label': '协同关系', 'color': '#2196F3', 'style': 'dotted', 'arrow': False},
            'verification': {'label': '验证关系', 'color': '#FF9800', 'style': 'dash-dot', 'arrow': True},
        }

        for rtype, info in relation_info.items():
            line_style = ""
            if info['style'] == 'solid':
                line_style = f"border-bottom: 3px solid {info['color']};"
            elif info['style'] == 'dashed':
                line_style = f"border-bottom: 3px dashed {info['color']};"
            elif info['style'] == 'dotted':
                line_style = f"border-bottom: 3px dotted {info['color']};"
            else:
                line_style = f"border-bottom: 3px dashed {info['color']}; border-bottom-style: dashed;"

            arrow_html = ""
            if info['arrow']:
                arrow_html = f'<span style="color:{info["color"]};font-size:16px;">→</span>'

            relation_legends += f'''
            <div style="display:flex;align-items:center;gap:8px;margin:6px 0;">
                <div style="width:30px;height:0;{line_style}"></div>
                {arrow_html}
                <span style="color:{info['color']};font-size:13px;">{info['label']}</span>
            </div>'''

        # 行业颜色图例
        industry_legends = ""
        industry_colors = self.viz_config.get('industry_colors', {})
        for industry, colors in industry_colors.items():
            industry_legends += f'''
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
                <div style="width:14px;height:14px;border-radius:3px;background:{colors['primary']};border:2px solid {colors['border']};"></div>
                <span style="color:#E0E0E0;font-size:12px;">{industry}</span>
            </div>'''

        # 层级图例
        chain_level_config = self.viz_config.get('chain_level', {})
        level_legends = ""
        level_info = {
            'upstream': '上游（原材料/基础）',
            'midstream': '中游（制造/加工）',
            'downstream': '下游（应用/终端）',
        }
        for level, label in level_info.items():
            lc = chain_level_config.get(level, {})
            shape = lc.get('shape', 'dot')
            level_legends += f'''
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
                <div style="width:14px;height:14px;background:{lc.get('badge_color','#888')};border-radius:{'0' if shape=='diamond' else '50%' if shape=='dot' else '3px'};transform:{'rotate(45deg) scale(0.7)' if shape=='diamond' else 'none'};"></div>
                <span style="color:#E0E0E0;font-size:12px;">{label}</span>
            </div>'''

        # 市值规模图例
        size_legends = ""
        market_cap_config = self.viz_config.get('market_cap_size', {})
        for cap, info in market_cap_config.items():
            size = info.get('node_size', 15) // 3
            size_legends += f'''
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
                <div style="width:{size}px;height:{size}px;border-radius:50%;background:rgba(255,255,255,0.6);"></div>
                <span style="color:#E0E0E0;font-size:12px;">{cap}市值</span>
            </div>'''

        return f'''
        <div id="legend" style="
            position:fixed;bottom:20px;left:20px;z-index:1000;
            background:rgba(10,14,39,0.92);
            border:1px solid rgba(255,255,255,0.1);
            border-radius:10px;padding:15px;
            box-shadow:0 4px 20px rgba(0,0,0,0.5);
            font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;
            max-height:80vh;overflow-y:auto;
        ">
            <div style="font-size:14px;font-weight:bold;color:#4ECDC4;margin-bottom:10px;">图例说明</div>

            <div style="font-size:12px;color:#999;margin-bottom:6px;">关系类型</div>
            {relation_legends}

            <div style="height:1px;background:rgba(255,255,255,0.1);margin:10px 0;"></div>

            <div style="font-size:12px;color:#999;margin-bottom:6px;">行业分类</div>
            {industry_legends}

            <div style="height:1px;background:rgba(255,255,255,0.1);margin:10px 0;"></div>

            <div style="font-size:12px;color:#999;margin-bottom:6px;">产业链层级</div>
            {level_legends}

            <div style="height:1px;background:rgba(255,255,255,0.1);margin:10px 0;"></div>

            <div style="font-size:12px;color:#999;margin-bottom:6px;">市值规模</div>
            {size_legends}
        </div>
        '''

    def _build_statistics_panel(self, statistics: Dict) -> str:
        """构建统计面板HTML"""
        stats_rows = ""
        for rtype, info in statistics.items():
            type_labels = {
                'supply_chain': '供应链',
                'competition': '竞争',
                'collaboration': '协同',
                'verification': '验证',
            }
            type_colors = {
                'supply_chain': '#4CAF50',
                'competition': '#F44336',
                'collaboration': '#2196F3',
                'verification': '#FF9800',
            }
            label = type_labels.get(rtype, rtype)
            color = type_colors.get(rtype, '#888')

            stats_rows += f'''
            <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                <span style="color:{color};font-size:13px;">{label}</span>
                <div style="display:flex;gap:15px;">
                    <span style="color:#E0E0E0;font-size:12px;">总计: <b>{info.get('total', 0)}</b></span>
                    <span style="color:#888;font-size:11px;">跨行业: {info.get('cross_industry', 0)}</span>
                </div>
            </div>'''

        return f'''
        <div id="statistics" style="
            position:fixed;bottom:20px;right:20px;z-index:1000;
            background:rgba(10,14,39,0.92);
            border:1px solid rgba(255,255,255,0.1);
            border-radius:10px;padding:15px;
            box-shadow:0 4px 20px rgba(0,0,0,0.5);
            font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;
            min-width:250px;
        ">
            <div style="font-size:14px;font-weight:bold;color:#4ECDC4;margin-bottom:10px;">关系统计</div>
            {stats_rows}
        </div>
        '''

    def _build_filter_controls(self) -> str:
        """构建筛选控件HTML"""
        return '''
        <div id="filter-controls" style="
            position:fixed;top:60px;right:20px;z-index:1000;
            background:rgba(10,14,39,0.92);
            border:1px solid rgba(255,255,255,0.1);
            border-radius:10px;padding:12px;
            box-shadow:0 4px 20px rgba(0,0,0,0.5);
            font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;
        ">
            <div style="font-size:12px;font-weight:bold;color:#4ECDC4;margin-bottom:8px;">交互提示</div>
            <div style="font-size:11px;color:#999;line-height:1.8;">
                • 拖拽节点调整布局<br>
                • 滚轮缩放视图<br>
                • 悬停查看详细信息<br>
                • 点击节点高亮关联<br>
                • 右侧面板调节物理参数<br>
                • 双击节点聚焦子图
            </div>
        </div>
        '''

    def _build_tooltip_patch(self) -> str:
        """构建tooltip渲染修补JS（三种方式）"""
        return '''
        <script>
        // ============================================================
        // 修补 vis-network 9.x tooltip 渲染问题
        // 根因：Popup.setText 使用 innerText 渲染 tooltip，
        //       导致 HTML 标签显示为源代码
        //       第一次悬停可能正常（MutationObserver 初始捕获），
        //       后续悬停显示源代码（复用 .vis-tooltip 元素，Observer 漏检）
        //
        // 三种修补方式：
        //   方式一：实例修补 — 找到 Popup 实例，重写 setText
        //   方式二：MutationObserver — 监听 .vis-tooltip 子节点变化并修复
        //   方式三：原型修补 — 通过实例回溯构造函数，修补 prototype.setText
        // ============================================================
        (function patchTooltipRendering() {
            var patched = false; // 标记是否已成功修补

            // ============ 通用：innerHTM 替换 innerText 的 setText 实现 ============
            function patchedSetText(content) {
                if (typeof content === 'string') {
                    if (content === '') {
                        this.frame.innerHTML = '';
                        return;
                    }
                    this.frame.innerHTML = content; // 关键：innerHTML 替代 innerText
                } else if (content instanceof Element) {
                    while (this.frame.firstChild) {
                        this.frame.removeChild(this.frame.firstChild);
                    }
                    this.frame.appendChild(content);
                }
            }

            // ============ 方式一：Popup 实例修补 ============
            // 问题：原代码路径 network.manipulation.canvas.popup 不存在
            // 修正：遍历多条路径查找 popup 实例；
            //       若首次悬停前 popup 未创建，注册一次性 hover 事件，
            //       等首次悬停创建 popup 后立即修补
            function tryPatchInstance() {
                if (patched) return;
                var net = window.network;
                if (!net) { setTimeout(tryPatchInstance, 500); return; }

                // 多路径查找 popup 实例
                var popup = null;
                var paths = [
                    function() { return net.interactionHandler && net.interactionHandler.popup; },
                    function() { return net.manipulation && net.manipulation.canvas && net.manipulation.canvas.popup; },
                    function() { return net.canvas && net.canvas.popup; },
                    function() { return net.body && net.body.popup; },
                ];
                for (var i = 0; i < paths.length; i++) {
                    try {
                        popup = paths[i]();
                        if (popup && popup.frame && typeof popup.setText === 'function') break;
                        popup = null;
                    } catch(e) {}
                }

                if (popup) {
                    popup.setText = patchedSetText;
                    patched = true;
                    console.log('[产业链系统] 方式一：Popup实例setText修补成功');
                    return;
                }

                // popup 尚未创建（首次悬停前不存在），注册一次性 hover 事件
                var hoverHandler = function() {
                    setTimeout(function() {
                        var p = null;
                        for (var j = 0; j < paths.length; j++) {
                            try {
                                p = paths[j]();
                                if (p && p.frame && typeof p.setText === 'function') break;
                                p = null;
                            } catch(e) {}
                        }
                        if (p) {
                            p.setText = patchedSetText;
                            patched = true;
                            console.log('[产业链系统] 方式一（延迟）：Popup实例setText修补成功');
                            net.off('hoverNode', hoverHandler);
                            net.off('hoverEdge', hoverHandler);
                        }
                    }, 50);
                };
                net.on('hoverNode', hoverHandler);
                net.on('hoverEdge', hoverHandler);
            }

            // ============ 方式二：MutationObserver 监听修补 ============
            // 问题：原代码只检查 addedNodes 是否为 .vis-tooltip 元素，
            //       但后续悬停时 vis-network 复用 .vis-tooltip 元素只更新子节点，
            //       addedNodes 是文本节点而非 .vis-tooltip，检测失败
            // 修正：检查 mutation.target 是否为 .vis-tooltip 或其内部元素；
            //       用 isFixing 标记防止递归
            var isFixing = false;
            var tooltipTitles = {}; // 缓存：nodeId/edgeId → title HTML

            // 收集所有节点的 title HTML（用于方式二的精确修复）
            function collectTitles() {
                try {
                    if (typeof nodes !== 'undefined' && nodes.get) {
                        var allNodes = nodes.get();
                        for (var i = 0; i < allNodes.length; i++) {
                            if (allNodes[i].title) {
                                tooltipTitles['node_' + allNodes[i].id] = allNodes[i].title;
                            }
                        }
                    }
                } catch(e) {}
                try {
                    if (typeof edges !== 'undefined' && edges.get) {
                        var allEdges = edges.get();
                        for (var i = 0; i < allEdges.length; i++) {
                            if (allEdges[i].title) {
                                tooltipTitles['edge_' + allEdges[i].id] = allEdges[i].title;
                            }
                        }
                    }
                } catch(e) {}
            }

            var observer = new MutationObserver(function(mutations) {
                if (patched) { observer.disconnect(); return; }

                for (var m = 0; m < mutations.length; m++) {
                    var mutation = mutations[m];
                    if (isFixing) return;

                    // 查找受影响的 .vis-tooltip 元素
                    var tooltipEl = null;

                    // 检查 addedNodes（首次添加 .vis-tooltip 元素时）
                    for (var i = 0; i < mutation.addedNodes.length; i++) {
                        var node = mutation.addedNodes[i];
                        if (node.nodeType === 1) { // Element node
                            if (node.classList && node.classList.contains('vis-tooltip')) {
                                tooltipEl = node;
                                break;
                            }
                            // addedNode 可能是 .vis-tooltip 内部的元素
                            if (node.parentElement) {
                                var p = node.parentElement;
                                while (p && p !== document.body) {
                                    if (p.classList && p.classList.contains('vis-tooltip')) {
                                        tooltipEl = p;
                                        break;
                                    }
                                    p = p.parentElement;
                                }
                                if (tooltipEl) break;
                            }
                        }
                    }

                    // 检查 mutation.target（后续悬停时，vis-network 复用 .vis-tooltip，
                    // 只通过 innerText 替换子节点内容，此时 target 就是 .vis-tooltip 本身）
                    if (!tooltipEl && mutation.target) {
                        var target = mutation.target;
                        // target 可能就是 .vis-tooltip
                        if (target.nodeType === 1 && target.classList && target.classList.contains('vis-tooltip')) {
                            tooltipEl = target;
                        }
                        // 或者 target 是 .vis-tooltip 内部的文本节点/元素
                        else if (target.parentElement) {
                            var p = target.parentElement;
                            while (p && p !== document.body) {
                                if (p.classList && p.classList.contains('vis-tooltip')) {
                                    tooltipEl = p;
                                    break;
                                }
                                p = p.parentElement;
                            }
                        }
                    }

                    if (tooltipEl && !isFixing) {
                        // 获取 innerText 中的 HTML 标签字面量
                        var raw = tooltipEl.innerText || tooltipEl.textContent || '';
                        if (raw && (raw.indexOf('<div') !== -1 || raw.indexOf('<span') !== -1
                            || raw.indexOf('<b>') !== -1 || raw.indexOf('<hr') !== -1
                            || raw.indexOf('<br') !== -1))
                        {
                            isFixing = true;
                            try {
                                // 将 innerText 中的 HTML 标签字面量作为真正的 HTML 渲染
                                tooltipEl.innerHTML = raw;
                            } catch(e) {}
                            isFixing = false;
                        }
                    }
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true,
                characterData: true
            });

            // ============ 方式三：Popup 原型修补 ============
            // 问题：vis.Popup 不是公共 API，vis.Popup 为 undefined
            // 修正：通过实例的 constructor 回溯原型链；
            //       等首次悬停创建 popup 实例后，从实例获取 constructor.prototype
            function tryPatchPrototype() {
                if (patched) return;

                // 尝试直接访问 vis.Popup
                if (typeof vis !== 'undefined' && vis.Popup && vis.Popup.prototype) {
                    vis.Popup.prototype.setText = patchedSetText;
                    patched = true;
                    console.log('[产业链系统] 方式三：vis.Popup.prototype 修补成功');
                    observer.disconnect();
                    return;
                }

                // 通过实例的 constructor 回溯原型
                var net = window.network;
                if (net) {
                    var popup = null;
                    var paths = [
                        function() { return net.interactionHandler && net.interactionHandler.popup; },
                        function() { return net.manipulation && net.manipulation.canvas && net.manipulation.canvas.popup; },
                        function() { return net.canvas && net.canvas.popup; },
                        function() { return net.body && net.body.popup; },
                    ];
                    for (var i = 0; i < paths.length; i++) {
                        try {
                            popup = paths[i]();
                            if (popup && popup.frame && typeof popup.setText === 'function') break;
                            popup = null;
                        } catch(e) {}
                    }

                    if (popup && popup.constructor && popup.constructor.prototype) {
                        popup.constructor.prototype.setText = patchedSetText;
                        patched = true;
                        console.log('[产业链系统] 方式三：通过实例constructor回溯原型修补成功');
                        observer.disconnect();
                        return;
                    }
                }

                // 未找到，延迟重试
                if (!patched) {
                    setTimeout(tryPatchPrototype, 800);
                }
            }

            // ============ 初始化 ============
            // 方式一：立即尝试实例修补
            tryPatchInstance();

            // 方式三：页面加载后尝试原型修补
            if (document.readyState === 'complete') {
                setTimeout(function() { collectTitles(); tryPatchPrototype(); }, 300);
            } else {
                window.addEventListener('load', function() {
                    setTimeout(function() { collectTitles(); tryPatchPrototype(); }, 300);
                });
            }
        })();
        </script>
        '''    
        
    def _inject_custom_html(
        self,
        filepath: str,
        title: str,
        legend_items: Optional[Dict],
        statistics: Optional[Dict],
    ):
        """注入自定义HTML（标题栏、图例、统计面板等）"""
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入标题栏
        title_bar = self._build_title_bar(title)
        html = html.replace('<body>', f'<body>\n{title_bar}')

        # 注入图例
        if legend_items:
            legend_html = self._build_legend(legend_items)
            html = html.replace('</body>', f'{legend_html}\n</body>')

        # 注入统计面板
        if statistics:
            stats_html = self._build_statistics_panel(statistics)
            html = html.replace('</body>', f'{stats_html}\n</body>')

        # 注入自定义CSS
        custom_css = self._build_custom_css()
        html = html.replace('</head>', f'{custom_css}\n</head>')

        # 注入筛选控件
        filter_html = self._build_filter_controls()
        html = html.replace('</body>', f'{filter_html}\n</body>')

        # ★ 核心修复：注入JS修补vis-network的tooltip渲染
        tooltip_patch = self._build_tooltip_patch()
        html = html.replace('</body>', f'{tooltip_patch}\n</body>')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
    def _build_custom_css(self) -> str:
            """构建自定义CSS"""
            return '''
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background: #0a0e27 !important;
                    overflow: hidden;
                }
                #mynetwork {
                    margin-top: 55px;
                    height: calc(100vh - 55px) !important;
                }
                div.vis-network canvas {
                    outline: none;
                }
                .vis-tooltip {
                    background: rgba(10, 14, 39, 0.95) !important;
                    border: 1px solid rgba(78, 205, 196, 0.3) !important;
                    border-radius: 8px !important;
                    padding: 12px 16px !important;
                    font-family: 'Microsoft YaHei', 'Noto Sans SC', sans-serif !important;
                    color: #E0E0E0 !important;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.6) !important;
                    max-width: 380px !important;
                    line-height: 1.7 !important;
                    font-size: 13px !important;
                    word-wrap: break-word !important;
                }
                .vis-tooltip b {
                    color: #4ECDC4 !important;
                    font-weight: 600 !important;
                }
                .vis-tooltip hr {
                    border: none !important;
                    border-top: 1px solid rgba(78, 205, 196, 0.3) !important;
                    margin: 6px 0 !important;
                }
                .vis-tooltip .tooltip-industry {
                    color: #FFD93D;
                }
                .vis-tooltip .tooltip-level {
                    color: #FF9800;
                }
            </style>
            '''