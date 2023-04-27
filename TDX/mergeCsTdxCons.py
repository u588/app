from sqlalchemy import create_engine
import requests
import re
from lxml import etree
import pandas as pd
import random
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/tdxIndex')


tdx= pd.read_sql('tdxIndexCons', eng)
cs = pd.read_sql('csIndexCons', eng)

