from pyspark.sql import SparkSession
import re
import pandas as pd

spark = SparkSession.builder.remote("sc://10.88.1.8:15002").getOrCreate()

columns = ["id","name"]
data = [(1,"Sarah"),(2,"Maria")]
df = spark.createDataFrame(data).toDF(*columns)

df.show()


df1 = pd.DataFrame(columns=['IndexCode', 'IndexName', 'StockCode', 'StockName','IndexSTL'])
df2 = pd.DataFrame(columns=['IndexCode', 'IndexName','IndexSTL', 'Num', 'From'])

dfi = spark.createDataFrame(df1)
dfs = spark.createDataFrame(df2)