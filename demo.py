import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
import time
import os
load_dotenv()   

## Load the GROQ and OpenAI API KEY 
groq_api_key = os.getenv('GROQ_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Set the title of the Streamlit app
st.title("Gemma Model Document Q&A")
    
# Initialize the ChatGroq model with the provided API key and model name
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")

# Define the prompt template for the chat model
prompt = ChatPromptTemplate.from_template(
"""
Answer the questions based on the provided context only.
Please provide the most accurate response based on the question
<context>
{context}
<context>
Questions:{input}
"""
)

# Function to create vector embeddings
def vector_embedding():
    if "vectors" not in st.session_state:
        # Initialize embeddings using GoogleGenerativeAIEmbeddings
        st.session_state.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        # Load documents from the specified directory
        st.session_state.loader = PyPDFDirectoryLoader("./us_census")
        st.session_state.docs = st.session_state.loader.load()
        # Split documents into chunks
        st.session_state.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        st.session_state.final_documents = st.session_state.text_splitter.split_documents(st.session_state.docs[:20])
        # Create vector store using FAISS
        st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings) 


# Input field for user to enter their question
prompt1 = st.text_input("Enter Your Question From Documents")

# Button to trigger document embedding
if st.button("Documents Embedding"):
    vector_embedding()
    st.write("Vector Store DB Is Ready")



# If a question is entered, process it
if prompt1:
    # Create a document chain using the chat model and prompt
    document_chain = create_stuff_documents_chain(llm, prompt)
    # Retrieve relevant documents using the vector store
    retriever = st.session_state.vectors.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    # Measure the response time
    start = time.process_time()
    response = retrieval_chain.invoke({'input': prompt1})
    print("Response time:", time.process_time() - start)
    # Display the response
    st.write(response['answer'])

    # With a Streamlit expander, show the document similarity search results
    with st.expander("Document Similarity Search"):
        # Find and display the relevant chunks
        for i, doc in enumerate(response["context"]):
            st.write(doc.page_content)
            st.write("--------------------------------") 

    
