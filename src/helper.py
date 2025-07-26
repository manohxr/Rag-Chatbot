# helper.py
import os
from dotenv import load_dotenv
from langchain.document_loaders import DirectoryLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=pinecone_api_key)
client = OpenAI()

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

def load_pdf_files(path):
    if os.path.isdir(path):
        loader = DirectoryLoader(path)
    else:
        loader = PyPDFLoader(path)
    return loader.load()

def chunk_data(docs, chunk_size=800, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)

def convert_chunks_to_list(chunks):
    return [{"_id": f"rec{i}", "chunk_text": doc.page_content} for i, doc in enumerate(chunks, 1)]

def update_index(username, namespace):
    # This assumes your file is in: Data/{username}/{namespace}.pdf
    pdf_path = f'Data/{username}/{namespace}.pdf'
    docs = load_pdf_files(pdf_path)  # Load ONLY the uploaded file

    chunks = chunk_data(docs)
    text_list = convert_chunks_to_list(chunks)

    if not text_list:
        return f"No chunks found for '{namespace}'.", 0

    index = create_or_get_index(username)
    for i in range(0, len(text_list), 96):
        index.upsert_records(namespace, text_list[i:i+96])

    return f"Index updated with {len(text_list)} chunks under namespace '{namespace}'.", len(text_list)

def retrieve_query(query, username, namespace, k=4):
    index = create_or_get_index(username)
    results = index.search(
        namespace=namespace,
        query={"inputs": {"text": query}, "top_k": k},
        fields=["chunk_text"]
    )
    hits = results['result']['hits']
    docs = []
    for hit in hits:
        if 'fields' in hit:
            docs.append(Document(
                page_content=hit['fields']['chunk_text'],
                metadata={"score": hit.get('_score', 0.0)}
            ))
    return docs

def answer_query_stream(query, username, namespace=None):
    if namespace:
        docs = retrieve_query(query, username, namespace)
        threshold = 0.2
        relevant_docs = [doc for doc in docs if doc.metadata.get("score", 0) >= threshold]

        if relevant_docs:
            context = "\n\n".join(doc.page_content for doc in relevant_docs)
            prompt = f"Answer the user using ONLY the context below if possible.\n\nContext:\n{context}\n\nQuestion:\n{query}"
        else:
            prompt = query
    else:
        # fallback to base LLM
        prompt = query

    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        stream=True
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content if chunk.choices[0].delta else None
        if content:
            yield content
