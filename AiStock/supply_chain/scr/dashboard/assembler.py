from plotly.subplots import make_subplots
import plotly.graph_objects as go
from typing import List

class DashboardAssembler:
    def __init__(self, specs: List[List[dict]], titles: List[str]):
        self.specs = specs
        self.titles = titles
        
    def compose(self, figures: List[go.Figure]) -> go.Figure:
        rows = len(self.specs)
        cols = len(self.specs[0])
        fig = make_subplots(
            rows=rows, cols=cols, subplot_titles=self.titles,
            specs=self.specs, vertical_spacing=0.06, horizontal_spacing=0.06
        )
        
        for idx, subfig in enumerate(figures):
            r = (idx // cols) + 1
            c = (idx % cols) + 1
            for trace in subfig.data:
                fig.add_trace(trace, row=r, col=c)
                
        fig.update_layout(
            height=2000, width=1600,
            title_text="<b>十五五十大投资方向全景图谱</b>",
            showlegend=True, font_size=10
        )
        return fig