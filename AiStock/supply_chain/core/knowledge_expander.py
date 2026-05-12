"""
知识扩充模块
对产业链关系进行专业深度扩充，增加隐性关系和行业洞察
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ExpandedRelation:
    """扩充的关系"""
    source: str
    target: str
    source_uid: str
    target_uid: str
    relation_type: str
    label: str
    weight: int
    description: str
    insight: str  # 专业洞察
    is_cross_industry: bool = False


class KnowledgeExpander:
    """知识扩充器，基于行业知识图谱对关系进行专业深度扩充"""

    def __init__(
        self,
        targets: List[Dict],
        chain_structures: Dict,
        name_map: Dict[str, Dict],
    ):
        """
        初始化知识扩充器

        Args:
            targets: 标的数据列表
            chain_structures: 产业链结构
            name_map: 标的名称→标的数据映射
        """
        self.targets = targets
        self.chain_structures = chain_structures
        self.name_map = name_map
        self._expanded: List[ExpandedRelation] = []

    def expand(self) -> List[ExpandedRelation]:
        """
        执行知识扩充，返回扩充后的关系列表

        扩充策略：
        1. 产业链上下游隐性关联挖掘
        2. 技术同源性协同关系
        3. 客户重叠竞争关系
        4. 资本/股权关联
        5. 政策驱动关联
        """
        self._expand_implicit_supply_chain()
        self._expand_tech_synergy()
        self._expand_policy_driven()
        self._expand_customer_overlap()
        self._expand_ecosystem_bonds()

        print(f"[KnowledgeExpander] 扩充关系数: {len(self._expanded)}")
        return self._expanded

    def _expand_implicit_supply_chain(self):
        """挖掘隐性供应链关系"""

        implicit_relations = [
            # 硅片→封测的隐性供应链
            {
                'source': '沪硅产业', 'target': '长电科技',
                'label': '硅片→封装', 'weight': 3,
                'description': '大硅片晶圆经代工后进入封测环节，形成硅片→代工→封测完整链条',
                'insight': '国产12英寸硅片量产突破后，国产封测产能利用率有望同步提升'
            },
            {
                'source': '沪硅产业', 'target': '通富微电',
                'label': '硅片→封装', 'weight': 3,
                'description': '大硅片供应通富微电先进封装产线',
                'insight': '硅片国产化率提升将降低封测企业原材料成本'
            },
            # SiC衬底→功率器件→新能源车的传导
            {
                'source': '天岳先进', 'target': '三安光电',
                'label': '衬底→器件协同', 'weight': 4,
                'description': '天岳SiC衬底可供应三安光电外延器件制造',
                'insight': 'SiC衬底国产化是降低车规SiC器件成本的关键瓶颈'
            },
            # 光刻胶→晶圆厂
            {
                'source': '南大光电', 'target': '华虹公司',
                'label': '光刻胶验证', 'weight': 3,
                'description': '南大光电ArF光刻胶在特色工艺产线验证中',
                'insight': 'ArF光刻胶国产化是28nm以下制程自主可控的核心环节'
            },
            # 靶材→封测耗材
            {
                'source': '江丰电子', 'target': '长电科技',
                'label': '靶材→封测', 'weight': 2,
                'description': '超高纯靶材溅射薄膜在封测基板/凸块工艺中应用',
                'insight': '先进封装对高纯金属薄膜需求增长，靶材企业受益'
            },
            # 锂→电池→储能
            {
                'source': '盐湖股份', 'target': '比亚迪',
                'label': '锂盐供应', 'weight': 4,
                'description': '盐湖提锂碳酸锂供应比亚迪电池产线',
                'insight': '盐湖提锂成本优势在锂价下行周期中更显韧性'
            },
            {
                'source': '赣锋锂业', 'target': '宁德时代',
                'label': '锂资源供应', 'weight': 4,
                'description': '赣锋锂业氢氧化锂/碳酸锂供应宁德时代',
                'insight': '锂价周期波动下，长协锁量保障电池厂原料稳定'
            },
            # 碳纤维→风电→新能源
            {
                'source': '中复神鹰', 'target': '阳光电源',
                'label': '碳纤维→风电叶片', 'weight': 2,
                'description': '碳纤维用于风电叶片拉挤工艺，风电是光储系统配套',
                'insight': '碳纤维降本推动风电叶片大型化，间接利好新能源系统'
            },
            # 磁材→机器人电机
            {
                'source': '金力永磁', 'target': '鸣志电器',
                'label': '磁材→电机', 'weight': 3,
                'description': '高性能钕铁硼磁材是人形机器人空心杯/步进电机核心材料',
                'insight': '人形机器人放量将显著拉动高性能磁材需求增量'
            },
            {
                'source': '正海磁材', 'target': '江苏雷利',
                'label': '磁材→微特电机', 'weight': 2,
                'description': '钕铁硼磁材供应微特电机制造',
                'insight': '机器人微特电机对磁材性能要求极高，高端磁材受益'
            },
            # GPU→大模型→办公AI
            {
                'source': '海光信息', 'target': '金山办公',
                'label': '算力→AI办公', 'weight': 3,
                'description': '海光DCU提供AI推理算力支撑WPS AI功能',
                'insight': '国产算力+国产办公软件形成信创AI闭环'
            },
            # 前驱体→存储芯片
            {
                'source': '雅克科技', 'target': '长电科技',
                'label': '前驱体→封装', 'weight': 3,
                'description': '前驱体材料在先进封装TSV/RDL工艺中关键应用',
                'insight': '前驱体是先进封装介质层沉积的核心材料'
            },
        ]

        for r in implicit_relations:
            src = self.name_map.get(r['source'])
            tgt = self.name_map.get(r['target'])
            if src and tgt:
                self._expanded.append(ExpandedRelation(
                    source=r['source'],
                    target=r['target'],
                    source_uid=src['uid'],
                    target_uid=tgt['uid'],
                    relation_type='supply_chain',
                    label=r['label'],
                    weight=r['weight'],
                    description=r['description'],
                    insight=r['insight'],
                    is_cross_industry=src['一级方向'] != tgt['一级方向'],
                ))

    def _expand_tech_synergy(self):
        """挖掘技术同源性协同关系"""

        tech_synergies = [
            # 半导体设备同源技术
            {
                'source': '北方华创', 'target': '拓荆科技',
                'label': '薄膜+刻蚀工艺协同', 'weight': 3,
                'description': '北方华创PVD+拓荆PECVD在晶圆产线形成薄膜工艺组合',
                'insight': '刻蚀与薄膜沉积是前道工艺的核心步骤，设备组合采购率高'
            },
            {
                'source': '中微公司', 'target': '华海清科',
                'label': '刻蚀+CMP协同', 'weight': 3,
                'description': '刻蚀后CMP平坦化是标准工艺流程，设备配套使用',
                'insight': '刻蚀深度控制与CMP平坦化精度互相关联'
            },
            # AI算力技术同源
            {
                'source': '寒武纪', 'target': '景嘉微',
                'label': 'AI芯片+GPU协同', 'weight': 3,
                'description': '寒武纪AI推理芯片+景嘉微GPU在信创市场形成算力组合',
                'insight': '信创市场对AI芯片+图形GPU组合方案需求增长'
            },
            # 高温合金→航发+燃气轮机
            {
                'source': '钢研高纳', 'target': '图南股份',
                'label': '高温合金技术同源', 'weight': 3,
                'description': '同属高温合金赛道，铸造/粉末冶金技术路线互补',
                'insight': '高温合金在航发/燃机/核电多领域应用，技术壁垒极高'
            },
            # 传感器技术同源
            {
                'source': '柯力传感', 'target': '汉威科技',
                'label': '传感技术同源', 'weight': 2,
                'description': '力学传感器+气体传感器在物联网/机器人领域技术互补',
                'insight': '多模态传感器融合是机器人感知系统的发展方向'
            },
            # CRO技术同源
            {
                'source': '康龙化成', 'target': '昭衍新药',
                'label': 'CRO技术互补', 'weight': 3,
                'description': '康龙临床前CRO+昭衍安评CRO在创新药研发链条互补',
                'insight': '一体化CRO服务是行业趋势，临床前+安评组合增强客户粘性'
            },
            # 碳纤维技术同源
            {
                'source': '光威复材', 'target': '中简科技',
                'label': '碳纤维技术同源', 'weight': 3,
                'description': 'T300-T1000级碳纤维技术积累，军品/民品路线互补',
                'insight': '碳纤维国产化从T300到T1000逐级突破，技术积累是核心壁垒'
            },
            # 光模块+光纤器件
            {
                'source': '中际旭创', 'target': '光迅科技',
                'label': '光通信技术同源', 'weight': 3,
                'description': '光模块+光器件在硅光/CPO技术路线上协同',
                'insight': '硅光技术是光通信下一代技术方向，模块+器件厂商深度协同'
            },
        ]

        for r in tech_synergies:
            src = self.name_map.get(r['source'])
            tgt = self.name_map.get(r['target'])
            if src and tgt:
                self._expanded.append(ExpandedRelation(
                    source=r['source'],
                    target=r['target'],
                    source_uid=src['uid'],
                    target_uid=tgt['uid'],
                    relation_type='collaboration',
                    label=r['label'],
                    weight=r['weight'],
                    description=r['description'],
                    insight=r['insight'],
                    is_cross_industry=src['一级方向'] != tgt['一级方向'],
                ))

    def _expand_policy_driven(self):
        """挖掘政策驱动关联"""

        policy_relations = [
            # 信创政策
            {
                'source': '龙芯中科', 'target': '紫光国微',
                'label': '信创双核', 'weight': 4,
                'description': '龙芯CPU+紫光FPGA是信创核心芯片组合',
                'insight': '信创政策驱动党政军领域CPU+FPGA组合采购'
            },
            {
                'source': '金山办公', 'target': '龙芯中科',
                'label': '信创办公闭环', 'weight': 3,
                'description': 'WPS AI适配龙芯平台，形成信创办公闭环',
                'insight': '国产CPU+国产办公软件是信创基础软件栈核心'
            },
            # 新能源政策
            {
                'source': '隆基绿能', 'target': '宁德时代',
                'label': '双碳政策双驱动', 'weight': 3,
                'description': '光伏+储能是双碳政策两大核心赛道',
                'insight': '双碳政策驱动光伏+储能装机量持续高增长'
            },
            # 半导体国产化政策
            {
                'source': '北方华创', 'target': '中微公司',
                'label': '国产设备双支柱', 'weight': 4,
                'description': '国产半导体设备两大支柱，政策重点扶持',
                'insight': '大基金+地方基金重点投向国产半导体设备领域'
            },
            # 低空经济政策
            {
                'source': '中信海直', 'target': '莱斯信息',
                'label': '低空经济政策双受益', 'weight': 3,
                'description': '低空运营+空管系统是低空经济政策两大受益方向',
                'insight': '低空经济政策推动空域开放与基础设施建设加速'
            },
            # 数据要素政策
            {
                'source': '人民网', 'target': '易华录',
                'label': '数据要素政策双受益', 'weight': 3,
                'description': '数据确权+数据存储是数据要素政策两大抓手',
                'insight': '数据二十条政策推动数据确权与数据资产入表加速'
            },
        ]

        for r in policy_relations:
            src = self.name_map.get(r['source'])
            tgt = self.name_map.get(r['target'])
            if src and tgt:
                self._expanded.append(ExpandedRelation(
                    source=r['source'],
                    target=r['target'],
                    source_uid=src['uid'],
                    target_uid=tgt['uid'],
                    relation_type='collaboration',
                    label=r['label'],
                    weight=r['weight'],
                    description=r['description'],
                    insight=r['insight'],
                    is_cross_industry=src['一级方向'] != tgt['一级方向'],
                ))

    def _expand_customer_overlap(self):
        """挖掘客户重叠竞争关系"""

        overlap_relations = [
            # 共享中芯国际作为客户
            {
                'source': '北方华创', 'target': '中微公司',
                'label': '同客户设备竞争', 'weight': 4,
                'description': '北方华创与中微公司均向中芯国际等晶圆厂供应设备，存在客户重叠竞争',
                'insight': '国产设备厂商在晶圆厂客户层面存在市场份额竞争'
            },
            {
                'source': '华特气体', 'target': '南大光电',
                'label': '特气/光刻胶客户重叠', 'weight': 3,
                'description': '华特电子特气与南大光电前驱体/光刻胶面向相同晶圆厂客户',
                'insight': '材料厂商向同一晶圆厂客户交叉销售，存在品类拓展竞争'
            },
            # 共享新能源车企客户
            {
                'source': '金力永磁', 'target': '正海磁材',
                'label': '车规磁材客户重叠', 'weight': 3,
                'description': '均面向新能源车企供应车规钕铁硼磁材',
                'insight': '车规磁材认证周期长，客户粘性强，先发优势明显'
            },
            # CRO客户重叠
            {
                'source': '药明康德', 'target': '康龙化成',
                'label': 'CRO客户重叠竞争', 'weight': 4,
                'description': '药明与康龙均服务全球创新药企，客户池高度重叠',
                'insight': '全球TOP20药企是CRO核心客户，市场份额竞争激烈'
            },
            # 服务器客户重叠
            {
                'source': '浪潮信息', 'target': '中科曙光',
                'label': 'AI服务器客户竞争', 'weight': 4,
                'description': '浪潮与曙光在互联网/运营商AI服务器市场直接竞争',
                'insight': '互联网大厂是AI服务器最大买家，份额争夺白热化'
            },
        ]

        for r in overlap_relations:
            src = self.name_map.get(r['source'])
            tgt = self.name_map.get(r['target'])
            if src and tgt:
                self._expanded.append(ExpandedRelation(
                    source=r['source'],
                    target=r['target'],
                    source_uid=src['uid'],
                    target_uid=tgt['uid'],
                    relation_type='competition',
                    label=r['label'],
                    weight=r['weight'],
                    description=r['description'],
                    insight=r['insight'],
                    is_cross_industry=src['一级方向'] != tgt['一级方向'],
                ))

    def _expand_ecosystem_bonds(self):
        """挖掘产业生态圈关联"""

        ecosystem_relations = [
            # 半导体生态圈
            {
                'source': '中芯国际', 'target': '长电科技',
                'label': '代工→封测生态', 'weight': 5,
                'description': '中芯国际晶圆代工+长电科技封测形成国产芯片完整制造生态',
                'insight': '代工+封测一体化服务是吸引Fabless客户的核心竞争力'
            },
            # AI算力生态圈
            {
                'source': '中科曙光', 'target': '浪潮信息',
                'label': 'AI算力生态竞争', 'weight': 4,
                'description': '曙光(海光生态)与浪潮(多元生态)在AI算力集群市场生态竞争',
                'insight': 'AI算力生态绑定芯片厂商，生态竞争实质是芯片路线竞争'
            },
            # 新能源车生态
            {
                'source': '宁德时代', 'target': '阳光电源',
                'label': '动力电池+光储生态', 'weight': 4,
                'description': '宁德时代电池+阳光电源逆变器形成光储充一体化生态',
                'insight': '光储充一体化是新能源终端场景的标准解决方案'
            },
            # 军工电子生态
            {
                'source': '紫光国微', 'target': '航天电器',
                'label': '军工电子生态', 'weight': 4,
                'description': 'FPGA+连接器/继电器构成军工电子核心生态组合',
                'insight': '军工电子生态强调自主可控，国产芯片+国产元器件成标配'
            },
            # 人形机器人生态
            {
                'source': '汇川技术', 'target': '绿的谐波',
                'label': '运动控制生态', 'weight': 5,
                'description': '伺服驱动+谐波减速器构成机器人运动控制核心生态',
                'insight': '运动控制系统是人形机器人区别于工业机器人的核心差异化环节'
            },
            {
                'source': '鸣志电器', 'target': '兆威机电',
                'label': '灵巧手生态', 'weight': 4,
                'description': '空心杯电机+微型齿轮箱构成灵巧手传动生态',
                'insight': '灵巧手是人形机器人精细化操作的标志性部件'
            },
        ]

        for r in ecosystem_relations:
            src = self.name_map.get(r['source'])
            tgt = self.name_map.get(r['target'])
            if src and tgt:
                self._expanded.append(ExpandedRelation(
                    source=r['source'],
                    target=r['target'],
                    source_uid=src['uid'],
                    target_uid=tgt['uid'],
                    relation_type='collaboration',
                    label=r['label'],
                    weight=r['weight'],
                    description=r['description'],
                    insight=r['insight'],
                    is_cross_industry=src['一级方向'] != tgt['一级方向'],
                ))

    @property
    def expanded_relations(self) -> List[ExpandedRelation]:
        """获取扩充关系列表"""
        return self._expanded

    def get_expanded_by_type(self, relation_type: str) -> List[ExpandedRelation]:
        """按类型获取扩充关系"""
        return [r for r in self._expanded if r.relation_type == relation_type]