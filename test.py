
from mootdx.quotes import Quotes
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain.docstore.document import Document


client = Quotes.factory(market='std')
txt = client.F10('301117', '股东研究')

model = Ollama(base_url='http://10.3.68.3:11434', model='llama3.1:8b-instruct-q8_0')

prompt_template = """Write a professional verbose summary of the following:
{text}
PROFESSIONAL VERBOSE SUMMARY IN CHINESE:"""

PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])

chain = load_summarize_chain(model, chain_type="stuff", prompt=PROMPT)

docs = [Document(page_content=txt)]

chain.invoke(input=docs, return_only_outputs=True) 
