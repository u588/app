from pyspark.sql import SparkSession

spark = SparkSession.builder.remote("sc://10.88.1.8:15002").getOrCreate()

columns = ["id","name"]
data = [(1,"Sarah"),(2,"Maria")]
df = spark.createDataFrame(data).toDF(*columns)
df.show()