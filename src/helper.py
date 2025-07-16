# helper.py
import os
from dotenv import load_dotenv
from langchain.document_loaders import DirectoryLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.chains.question_answering import load_qa_chain
from langchain.chat_models import ChatOpenAI
from pinecone import Pinecone

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=pinecone_api_key)

def create_or_get_index(username):
    if not pc.has_index(username):
        pc.create_index_for_model(
            name=username,
            cloud="aws",
            region="us-east-1",
            embed={"model": "llama-text-embed-v2", "field_map": {"text": "chunk_text"}}
        )
    index = pc.Index(
        host=f"https://{username}-uzat91r.svc.aped-4627-b74a.pinecone.io"
    )
    return index

def load_pdf_files(user_folder):
    loader = DirectoryLoader(user_folder, glob="*.pdf", loader_cls=PyPDFLoader)
    return loader.load()

def chunk_data(docs, chunk_size=800, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)

def convert_chunks_to_list(chunks):
    return [{"_id": f"rec{i}", "chunk_text": doc.page_content} for i, doc in enumerate(chunks, 1)]

def update_index(username):
    index = create_or_get_index(username)
    docs = load_pdf_files(f'Data/{username}')
    chunks = chunk_data(docs)
    text_list = convert_chunks_to_list(chunks)
    for i in range(0, len(text_list), 96):
        index.upsert_records("example-namespace", text_list[i:i+96])
    return f"Index updated with {len(text_list)} chunks."

def retrieve_query(query, username, k=4):
    index = create_or_get_index(username)
    results = index.search(
        namespace="example-namespace",
        query={"inputs": {"text": query}, "top_k": k},
        fields=["chunk_text"]
    )
    hits = results['result']['hits']
    return [Document(page_content=hit['fields']['chunk_text']) for hit in hits if 'fields' in hit]

def answer_query(query, username):
    docs = retrieve_query(query, username)
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.5)
    chain = load_qa_chain(llm, chain_type="stuff")
    if docs:
        return chain.invoke({"input_documents": docs, "question": query})["output_text"]
    else:
        # fallback to direct LLM if no docs
        return llm.invoke(query).content
