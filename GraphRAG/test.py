# https://blog.csdn.net/weixin_43816875/article/details/139832298

#!/usr/bin/python 
# -*- coding: <utf-8> -*-
from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.graphs import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain.llms import Ollama
import os

# 设置api_key
os.environ["DASHSCOPE_API_KEY"] = "sk-key"
llm = Ollama(base_url='http://10.3.68.3:11434', model="qwen2:7b-instruct-q5_K_M")
# 7687


#链接neo4j 账号密码
username = "neo4j"
password = "syslog6^"
url = "10.3.18.50"
database = "test"

graph = Neo4jGraph(
    url=url,
    username=username,
    password=password
)

# LLMGraphTransformer模块 构建图谱
llm_transformer = LLMGraphTransformer(llm=llm)
# 导入文档————参考链接中居里夫人那段文本
raw_documents = TextLoader(autodetect_encoding=True,file_path="/home/ts/grahpRag/1.txt").load()
# 将文本分割成每个包含20个tokens的块，并且这些块之间没有重叠
text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=20, chunk_overlap=0
)
# Chunk the document
documents = text_splitter.split_documents(raw_documents)
# 打印原始文档内容
print(f"Raw Document Content: {raw_documents[0].page_content}")
# 打印分块后的文档内容
for i, doc in enumerate(documents):
    print(f"Chunk {i}: {doc.page_content}")
# 打印转换过程中的中间结果
graph_documents = llm_transformer.convert_to_graph_documents(documents)
for i, graph_doc in enumerate(graph_documents):
    print(f"Graph Document {i}:")
    print(f"Nodes: {graph_doc.nodes}")
    print(f"Relationships: {graph_doc.relationships}")
