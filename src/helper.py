from langchain.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


#load the data from pdf file
def load_pdf_file(data):
    loader = DirectoryLoader(data, glob="*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()
    return documents


#chunking the data
def chunk_data(docs,chunk_size=800,chunk_overlap=50):
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=chunk_size,chunk_overlap=chunk_overlap)
    doc=text_splitter.split_documents(docs)
    return doc


#convert document to a list
def convert_doc_to_list(documents):
    text = []
    id = 1
    for doc in documents:
        page_number = doc.metadata['page']
        content = doc.page_content
        text.append(
        {
          "_id":"rec"+str(id),
          "chunk_text": content
        }
        )
        id+=1
    return text