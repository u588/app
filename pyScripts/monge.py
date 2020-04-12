import pymongo

# 创建连接
client = pymongo.MongoClient(host="10.145.254.51", port=27017)
# 连接probeb库
db = client['probeb']
# 打印库中所有集合名称
print(db.collection_names())
# 连接到test1这个集合
collection = db.test1

# 这条命令是查找rssi大于srssi小于erssi,stime大于stime，小于etime的数据以stime倒叙排列
sumdata = collection.find({"RSSI": {"$gt": int(srssi), "$lt": int(erssi)}, "stime": {"$gt": stime, "$lt": etime}}).sort([('stime', -1)])

#这条命令是查找rssi大于srssi小于erssi,stime大于stime小于etime 且mac等于search或者dmac等于search（search是个变量， "$options":"i"是为了不区分search内容的大小写）的数据，以stime倒叙排列
sumdata = collection.find({"RSSI": {"$gt": int(srssi), "$lt": int(erssi)}, "stime": {"$gt": stime, "$lt": etime}, "$or": [{"mac": {"$regex": search, "$options":"i"}}, {"dmac": {"$regex": search,"$options":"i"}}]}).sort([('stime', -1)])

# 现在查询的结果赋值给sumdata，如果想查出具体数据，可以使用for循环
for data in sumdata:
  print(data)

# 注意：在使用python操作MongoDB进行排序的时候，不能使用db.test1.find().sort({"name" : 1, "age" : 1}) 
# 否则会遇到如下异常：
# TypeError: if no direction is specified, key_or_list must be an instance of list 
# 解决方法：
# db.tes1t.find().sort([("name", 1), ("age" , 1)]) 
# 原因：在python中只能使用列表进行排序，不能使用字典