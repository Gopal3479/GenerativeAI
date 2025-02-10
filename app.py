import streamlit as st 
import os 
from langchain_groq import ChatGroq 
from langchain_community.document_loaders import WebBaseLoader 
from langchain.embeddings import AzureOpenAIEmbeddings,OpenAIEmbeddings,OllamaEmbeddings 
from langchain.text_splitter import RecursiveCharacterTextSplitter 
from langchain.chains.combine_documents import create_stuff_documents_chain 
from langchain_community.chat_models import AzureChatOpenAI 
from langchain_core.prompts import ChatPromptTemplate 
from langchain.chains import create_retrieval_chain 
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings  

import time 
 
from dotenv import load_dotenv 
load_dotenv()  
 
## Load the Azure OpenAI API key from environment variables 
# azure_openai_api_key = os.environ['AZURE_OPENAI_API_KEY'] 
# os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY") 
 
# os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_OPENAI_ENDPOINT") 
# os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")  
# os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY") 
groq_api_key = os.getenv('GROQ_API_KEY')
 
 
# Check if 'vector' is not in the session state 
if "vector" not in st.session_state: 
    # Initialize embeddings using OpenAIEmbeddings 
    st.session_state.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
     
    # Load documents from the specified URL with SSL verification disabled 
    # st.session_state.loader = WebBaseLoader("https://docs.smith.langchain.com/",verify_ssl=True) 
    st.session_state.loader = WebBaseLoader("https://titlecapture.com/blog/ai-in-title-insurance/") 
    st.session_state.docs = st.session_state.loader.load() 
 
    # Split the loaded documents into chunks 
    st.session_state.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200) 
    st.session_state.final_documents = st.session_state.text_splitter.split_documents(st.session_state.docs[:10]) 
     
    # Create vectors from the document chunks using FAISS 
    # st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings) 
    st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings) 
 
st.title("RAG using Open Source LLM Models And Azure OpenAI API") 
 
# Initialize the Chat model with the Azure OpenAI API key and model name 
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
 
# Create a document chain using the LLM and prompt template 
document_chain = create_stuff_documents_chain(llm,prompt) 
 
# Create a retriever from the vectors 
retriever = st.session_state.vectors.as_retriever() 
 
# Create a retrieval chain using the retriever and document chain 
retrieval_chain = create_retrieval_chain(retriever, document_chain) 
 
# Input field for the user to enter their prompt 
prompt = st.text_input("Input your prompt here")  
 
# If a prompt is entered, process it 
if prompt: 
    start = time.process_time() 
     
    # Invoke the retrieval chain with the user's prompt 
    response = retrieval_chain.invoke({"input": prompt}) 
     
    # Print the response time 
    print("Response time:", time.process_time() - start) 
     
    # Display the response in the Streamlit app 
    st.write(response['answer']) 
        # With a Streamlit expander, show the document similarity search results 
    with st.expander("Document Similarity Search"): 
        # Find and display the relevant chunks 
        for i, doc in enumerate(response["context"]): 
            st.write(doc.page_content) 
            st.write("--------------------------------") 


