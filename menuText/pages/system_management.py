# 系统管理
import streamlit as st
import streamlit_antd_components as sac

def system_management():
    col1, col2 = st.columns([1, 7])
    with col1:
        ot = sac.tree( 
            items=[  # 选项卡内容
                sac.TreeItem(
                    label='业务管理', icon=None, tag='hot',
                    children=[
                        sac.TreeItem(
                            label='工程建设',
                            ),
                        sac.TreeItem(label='建设工程'),
                        sac.TreeItem(label='住房保障'),
                        sac.TreeItem(label='住房公积金'),
                        sac.TreeItem(label='物业管理', icon='cup-hot')
                        ],
                    ),
                sac.TreeItem(
                    label='财务管理', icon='houses',
                    ),
                sac.TreeItem(label='报表管理', icon='cup-straw'),
                sac.TreeItem(label='系统设置', icon='car-front', tag=sac.Tag(label='hot', color='#ee82ee', icon='car-front')),
            ], 
            format_func=None,   # 项目标签格式化
            icon=None,  # 树上的引导程序图标
            height=660,  # 树的高度（px）
            open_all=False,  # 打开所有项目
            checkbox=False,  # 显示允许多选的复选框
            checkbox_strict=False,  # 父项和子项不关联 
            show_line=True,  # 显性的显示树节点之间的层级结构
            return_index=False,  # 返回值为索引
            on_change=None,  # 回调函数
            args=None,
            kwargs=None,
            key='sac_tree',
            ) 
    with col2:
        st.markdown(f'### {ot}')