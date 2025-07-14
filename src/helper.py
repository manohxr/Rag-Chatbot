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
index_name = "rag-openai"

# One-time index setup
def create_or_get_index():
    if not pc.has_index(index_name):
        pc.create_index_for_model(
            name=index_name,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "chunk_text"}
            }
        )
    index = pc.Index(
        host=f"https://{index_name}-uzat91r.svc.aped-4627-b74a.pinecone.io"
    )
    return index

index = create_or_get_index()  # keep warm

# Load all PDFs
def load_pdf_files(folder_path='Data/'):
    loader = DirectoryLoader(folder_path, glob="*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()
    return documents

# Chunk them
def chunk_data(docs, chunk_size=800, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)

# Convert to upsert format
def convert_chunks_to_list(chunks):
    text_list = []
    id_counter = 1
    for doc in chunks:
        text_list.append({
            "_id": "rec" + str(id_counter),
            "chunk_text": doc.page_content
        })
        id_counter += 1
    return text_list

# Upsert once
def update_index():
    docs = load_pdf_files()
    chunks = chunk_data(docs)
    text_list = convert_chunks_to_list(chunks)
    batch_size = 96

    x, y = 0, batch_size
    while x < len(text_list):
        index.upsert_records(
            "example-namespace",
            text_list[x:y]
        )
        x += batch_size
        y += batch_size

    return f"✅ Index updated with {len(text_list)} chunks."

# Query Pinecone
def retrieve_query(query, k=4):
    results = index.search(
        namespace="example-namespace",
        query={"inputs": {"text": query}, "top_k": k},
        fields=["chunk_text"]
    )

    hits = results['result']['hits']
    docs = []
    for hit in hits:
        text = hit.get('fields', {}).get('chunk_text', '')
        docs.append(Document(
            page_content=text,
            metadata={"id": hit.get('_id'), "score": hit.get('_score')}
        ))
    return docs

# Run QA
def answer_query(query):
    docs = retrieve_query(query)
    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.5)
    chain = load_qa_chain(llm, chain_type="stuff")
    response = chain.invoke({"input_documents": docs, "question": query})
    return response["output_text"]

