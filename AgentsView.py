# Import necessary modules and classes
from typing import Annotated, TypedDict
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_community.tools import ArxivQueryRun, WikipediaQueryRun
from langgraph.graph.message import add_messages
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from IPython.display import Image, display
from dotenv import load_dotenv
from graphviz import Source
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings 
from langchain_community.vectorstores import FAISS
import os
# Load environment variables from a .env file
load_dotenv()

# Set environment variables for API keys
# os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_OPENAI_ENDPOINT")
# os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY") 



# Directory containing census PDFs
CENSUS_DIR = "./us_census"

# Load PDFs and extract text
def load_census_pdfs(directory):
    documents = []
    for file in os.listdir(directory):
        if file.endswith(".pdf"):
            pdf_path = os.path.join(directory, file)
            loader = PyMuPDFLoader(pdf_path)
            docs = loader.load()
            documents.extend(docs)
    return documents

# Process and store the text as embeddings
def create_census_vectorstore():
    documents = load_census_pdfs(CENSUS_DIR)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)

    # Generate embeddings
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")  # Can be replaced with Azure AI or another provider
    vectorstore = FAISS.from_documents(texts, embeddings)

    return vectorstore

# Create vector store for census data
census_vectorstore = create_census_vectorstore()

# Define function for querying census data
def query_census_data(query):
    results = census_vectorstore.similarity_search(query, k=2)
    return "\n".join([doc.page_content for doc in results])

# Create census data tool
census_tool = Tool(
    name="Census_Data_Search",
    func=query_census_data,
    description="Retrieve census data insights based on user queries.",
)

# Define a prompt template for the chatbot
prompt_template = PromptTemplate(
    input_variables=["query"],
    template=(
        "You are an intelligent assistant that answers questions using Wikipedia and ArXiv.\n\n"
        "User Query: {query}\n"
        "Analyze the question, determine the best source (Wikipedia or ArXiv), and provide an informative response."
    )
)

# List of tools available to the chatbot
tools = [census_tool]

# Define a state dictionary with annotated messages
class State(TypedDict):
    messages: Annotated[list, add_messages]

# Initialize a state graph
graph_builder = StateGraph(State)

# Initialize conversation memory
# memory = ConversationBufferMemory(memory_key="Chathistory", return_messages=True)

# Initialize the language model with the Groq API key
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Gemma2-9b-It")
# llm = AzureChatOpenAI(
#     deployment_name="gpt-4o-mini",
#     api_version="2024-05-01-preview",
#     temperature=0.7
# )


# Bind tools to the language model with memory
llm_with_tools = llm.bind_tools(tools=tools)

# Define the chatbot function
def chatbot(state: State):
    try:
        return {"messages": [llm_with_tools.invoke(state["messages"])]}
    except Exception as e:
        print(f"Error in chatbot function: {e}")
        return {"messages": []}

# Add nodes and edges to the state graph
graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

# Compile the state graph
graph = graph_builder.compile()

# Define user input 
user_input = input("Enter query here : ")

# Stream events through the graph
events = graph.stream(
    {"messages": [("user", user_input)]}, stream_mode="values"
)

# Process and print events
for event in events:
    try:
        event["messages"][-1].pretty_print()
    except Exception as e:
        print(f"Error processing event: {e}")

