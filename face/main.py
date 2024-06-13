import streamlit as st
from langchain.llms import LlamaCpp
from langchain import PromptTemplate
from langchain.embeddings import LlamaCppEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma


st.set_page_config(page_title="MiniCPM-Llama", page_icon="", layout="wide", )
 
path = "/Models/use/MiniCPM-Llama3-V-2_5-gguf/ggml-model-Q5_K_M.gguf"
model = LlamaCpp(model_path=path, n_ctx=8192, n_gpu_layer=40, n_batch=512)

template = """Q: 