import os
import streamlit as st
import time
import speech_recognition as sr
import pyttsx3
import threading
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
# Initialize session state for speech
if "speaking" not in st.session_state:
    st.session_state.speaking = False  # Track speech state
if "engine" not in st.session_state:
    st.session_state.engine = pyttsx3.init()  # Initialize text-to-speech engine

# Function to speak the response
def speak(text):
    """Convert text to speech and read it aloud."""
    if not st.session_state.speaking:
        st.session_state.speaking = True
        def run():
            st.session_state.engine.say(text)
            st.session_state.engine.runAndWait()
            st.session_state.speaking = False
        threading.Thread(target=run, daemon=True).start()  # Run speech in a separate thread

# Function to stop voice output
def stop_speech():
    """Stop voice output immediately."""
    if st.session_state.speaking:
        st.session_state.engine.stop()  # Stop the speech engine
        st.session_state.speaking = False

# Function to listen for voice input
def listen():
    """Listen for voice input and return recognized text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("Listening...")
        audio = recognizer.listen(source)  # Capture audio from the microphone
    try:
        text = recognizer.recognize_google(audio).lower()  # Recognize speech using Google API
        return text
    except sr.UnknownValueError:
        return "Sorry, I couldn't understand that."  # Handle unrecognized speech
    except sr.RequestError:
        return "Sorry, my speech service is down."  # Handle API request errors

# Load Azure API Key
groq_api_key = os.getenv('GROQ_API_KEY')

# Initialize session state for document processing
if "vector" not in st.session_state:
    st.session_state.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")  # Initialize embeddings
    st.session_state.loader = WebBaseLoader("https://titlecapture.com/blog/ai-in-title-insurance/")  # Load documents from web
    try:
        st.session_state.docs = st.session_state.loader.load()  # Load documents
        st.session_state.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)  # Split documents into chunks
        st.session_state.final_documents = st.session_state.text_splitter.split_documents(st.session_state.docs[:10])  # Split first 10 documents
        st.session_state.vectors = FAISS.from_documents(st.session_state.final_documents, st.session_state.embeddings)  # Create vector store
    except Exception as e:
        st.error(f"Error loading documents: {str(e)}")  # Handle document loading errors

st.title("RAG using Open Source LLM Models and Azure OpenAI API with Voice")  # Set the title of the Streamlit app

# Initialize Chat model
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")

# Define prompt template
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

# UI Layout
col1, col2 = st.columns([1, 1])
with col1:
    user_prompt = st.text_input("Input your prompt here")  # Text input for user prompt
with col2:
    if st.button("Use Voice Input"):
        st.write("Listening for voice input...")
        user_prompt = listen()  # Use voice input if button is pressed

if user_prompt:
    try:
        start = time.process_time()
        response = retrieval_chain.invoke({"input": user_prompt})  # Get response from retrieval chain
        response_text = response.get('answer', "No valid response found.")
        print("Response time:", time.process_time() - start)
        
        # Display response
        st.write("### Response:")
        st.write(response_text)
        
        # Speak response
        speak(response_text)
        
        # Show similarity search results
        with st.expander("Document Similarity Search"):
            for doc in response.get("context", []):
                st.write(doc.page_content)
                st.write("--------------------------------")
    except RuntimeError as e:
        st.error(f"An error occurred: {str(e)}")  # Handle runtime errors

# Stop voice button
if st.button("Stop Voice Output"):
    stop_speech()  # Stop voice output if button is pressed
