from src.helper import load_pdf_file, chunk_data, convert_doc_to_list
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()

pinecone_api_key = os.getenv("PINECONE_API_KEY")

extracted_data = load_pdf_file(data='Data')
text_chunks = chunk_data(extracted_data)
text_chunks_list = convert_doc_to_list(text_chunks)
print(len(text_chunks_list))


pc = Pinecone(api_key=pinecone_api_key)

index_name = "rag-openai"

if not pc.has_index(index_name):
    pc.create_index_for_model(
        name=index_name,
        cloud="aws",
        region="us-east-1",
        embed={
            "model":"llama-text-embed-v2",
            "field_map":{"text": "chunk_text"}
        }
    )



index = pc.Index(host="https://rag-openai-uzat91r.svc.aped-4627-b74a.pinecone.io")
x = 0
y = 96
for i in range(len(text_chunks_list)//96 + 1):
  index.upsert_records(
      "example-namespace",
      text_chunks_list[x:y]
  )
  x += 96
  y += 96

