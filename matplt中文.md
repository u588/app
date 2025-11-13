# 中文

* sudo apt install  fonts-noto-cjk
* 更新字体缓存 sudo fc-cache -fv
* 查看中文字体 fc-list :lang=zh
* 删除matplotlib字体缓存 rm ~/.cache/matplotlib/

## python配置

``` python
import matplotlib.pyplot  as plt

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False
```
