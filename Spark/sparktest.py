from pyspark.sql import SparkSession
import os
os.environ["PYARROW_IGNORE_TIMEZONE"] = "1"
import pyspark.pandas as ps



gn = open('D:/new_tdx/T0002/export/概念板块.txt', 'r',encoding="GBK", errors='ignore').read()
spark = SparkSession.builder.remote("sc://10.88.1.8:15002").getOrCreate()

spark.sql.
columns = ["id","name"]
data = [(1,"Sarah"),(2,"Maria")]
df = spark.createDataFrame(data).toDF(*columns)
df.show()


jdbcDF = spark.read \
    .format("jdbc") \
    .option("url", "jdbc:postgresql:10.145.254.56") \
    .option("dbtable", "schema.tdxIndexs") \
    .option("user", "sa") \
    .option("password", "11111111") \
    .load()