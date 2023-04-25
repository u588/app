from dataclasses import replace
from sqlalchemy import create_engine
import requests
import re
from lxml import etree
import pandas as pd
import random
import time

eng = create_engine('postgresql+psycopg2://sa:11111111@10.145.254.56:5432/csIndex')

Data = pd.read_sql('csIndexCon', eng )
Data.to_sql('csIndexCons', eng, if_exists='replace')