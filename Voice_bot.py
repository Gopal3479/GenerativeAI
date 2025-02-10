import os
import streamlit as st
import time
import speech_recognition as sr
import pyttsx3
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.document_loaders import WebBaseLoader
from dotenv import load_dotenv
import time
import os
load_dotenv()  

# Initialize Text-to-Speech engine
engine = pyttsx3.init()

def speak(text):
    """Convert text to speech and speak it."""
    engine.say(text)
    engine.runAndWait()

def listen():
    """Listen for voice input and return recognized text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source)
    
    try:
        # Recognize speech using Google Speech Recognition
        text = recognizer.recognize_google(audio).lower()
        return text
    except sr.UnknownValueError:
        # Handle unrecognized speech
        return "Sorry, I couldn't understand that."
    except sr.RequestError:
        # Handle request errors
        return "Sorry, my speech service is down."

def start_voice_command():
    """Wait for 'Hey Bot' activation phrase before listening for input."""
    while True:
        command = listen()
        if "hey bot" in command:
            # Remove activation phrase and return the command
            return command.replace("hey bot", "").strip()

# Load Azure API Key from environment variables
groq_api_key = os.getenv('GROQ_API_KEY')

# Initialize session state for vector store and document loader
if "vector" not in st.session_state:
    # Initialize embeddings model
    st.session_state.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    # Load documents from a web source
    st.session_state.loader = WebBaseLoader("https://titlecapture.com/blog/ai-in-title-insurance/")
    st.session_state.docs = st.session_state.loader.load()
    
    # Split documents into smaller chunks
    st.session_state.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    st.session_state.final_documents = st.session_state.text_splitter.split_documents(st.session_state.docs[:10])
    
    # Create FAISS vector store from documents
    st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings)

# Set the title of the Streamlit app
st.title("RAG using Open Source LLM Models and Azure OpenAI API with Voice")

# Initialize Chat model with API key and model name
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")

# Define prompt template for the chat model
prompt_template = ChatPromptTemplate.from_template(
    """
    Answer the questions based on the provided context only.
    Please provide the most accurate response based on the question.
    <context>
    {context}
    <context>
    Questions: {input}
    """
)

# Create document chain and retrieval chain
document_chain = create_stuff_documents_chain(llm, prompt_template)
retriever = st.session_state.vectors.as_retriever()
retrieval_chain = create_retrieval_chain(retriever, document_chain)

# Get input from user (via text or voice)
use_voice = st.checkbox("Use voice input")
if use_voice:
    st.write("Say 'Hey Bot' to start speaking...")
    user_prompt = start_voice_command()
else:
    user_prompt = st.text_input("Input your prompt here")

if user_prompt:
    start = time.process_time()
    # Invoke the retrieval chain with user input
    response = retrieval_chain.invoke({"input": user_prompt})
    response_text = response['answer']
    print("Response time:", time.process_time() - start)
    # Display response
    st.write(response_text)
    # Speak response
    speak(response_text)
    # Show similarity search results
    with st.expander("Document Similarity Search"):
        for doc in response["context"]:
            st.write(doc.page_content)
            st.write("--------------------------------")
