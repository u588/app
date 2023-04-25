import os

Path = 'H:/'
re = '：来源微信公众号：helpdx，后续资料更新请加群号：529075974'

for root, dirs, files in os.walk(Path):
    for name in files:
        NewFile = name.replace(re, '')
        os.rename(os.path.join(root, name), os.path.join(root, NewFile))
