from hugegraph.connection import PyHugeGraph
# init client
client = PyHugeGraph("127.0.0.1", "8080", user="admin", pwd="pwd", graph="hugegraph")

# schema
schema = client.schema()
schema.getVertexLabels()

# graph
g = client.graph()
g.getVertexById("1:tom")
g.close()

# gremlin
gremlin = client.gremlin()
gremlin.exec("g.V().limit(10)")