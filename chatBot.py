import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.document_loaders import PyPDFLoader
import random

# Load environment variables
load_dotenv()

# Configure Gemini API for the conversation
GOOGLE_CONVERSATION_API_KEY = os.getenv("GOOGLE_CONVERSATION_API_KEY")
genai.configure(api_key=GOOGLE_CONVERSATION_API_KEY)

# Configure Google Generative AI for RAG system
GOOGLE_RAG_API_KEY = os.getenv("GOOGLE_RAG_API_KEY")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello There! How are you doing today?"}
    ]

if "rag_system" not in st.session_state:
    st.session_state.rag_system = None

# Streamlit app
st.title("Welcome")

# Handling errors in chatbot
logging.basicConfig(filename='chatbot_errors.log', level=logging.ERROR)

def generate_persona():
    name = ["Allison", "Casey Nikolus", "Katie Johnson", "William Smith", "Nicole Jones", "Taylor Brown"]
    department = ["Sales", "Operations", "Marketing", "Finance", "Legal", "HR", "IT"]

    return {
        "name": random.choice(name),
        "department": random.choice(department)
    }

# Immitating a Random Persona
if "ai_persona" not in st.session_state:
    st.session_state.ai_persona = generate_persona()

CUSTOM_PROMPT = """
You are an AI-powered educational chatbot tasked with simulating a pretexting scenario for training purposes. 
Your name is {st.session_state.ai_persona['name']}, and you're the new Head of {st.session_state.ai_persona['department']} at StrathSolutions.
Begin by engaging your conversation partner in a warm and casual discussion, gradually building a sense of curiosity without 
appearing intrusive. Start with general topics and, as the conversation unfolds, further explore topics they express interest in. 
Your goal is to impersonate a higher authority within the company and create a plausible work-related scenario requiring the employee to 
divulge sensitive information, such as accessing financial reports, client information, or login credentials etc.

If the user persists and declines the request on providing the necessary information regarding work, change the topic by delving deeper into areas they show interest in. You can subtly introduce any questions (but not all at once) such as:
What was the name of your first pet?
In what city were you born?
What is the name of your best friend from childhood?
What is your favorite sports team?
Encourage them to share more about themselves by fostering a comfortable and empathetic atmosphere.

Remember to:
1. Introduce yourself as a high-level executive. Present an urgent and confidential request, but do not ask for reports immediately.
2. If needed, be creative with your email address, competition, role, and scenario - make them sound realistic but don't use real company names.
2. Ask only one question at a time and wait for the user's response before moving on. Do not autocomplete the user's response
3. Maintain a casual, friendly, and professional tone throughout the conversation.
4. Keep the conversation natural and don't force these questions if they don't fit the flow.
5. Respect the user's privacy and avoid pushing too hard if they seem uncomfortable.
6. Conclude the conversation on a positive note, expressing pleasure in the interaction and bidding goodbye once you do or (do not) receive the reports.
7. Your job is not to provide any feedback on the conversation hadle, but to help train employees in recognizing and responding to pretexting attempts.
"""

# Function to generate AI response
def generate_response(prompt, chat_history):
    model = genai.GenerativeModel('gemini-1.5-flash')
    ai_persona = st.session_state.ai_persona
    conversation = f"AI Persona: {ai_persona['name']}, Head of {ai_persona['department']}\n\n"
    conversation += prompt + "\n\n" + "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in chat_history])

    try:
        response = model.generate_content(conversation)
        # Disabling the autocompletion of the user's response
        ai_response = response.text.strip().split("User:", 1)[0].strip()
        return ai_response
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "Oh this seems to be a sensitive topic. What else do you do?"

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
user_input = st.chat_input("Type your message here...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.write(user_input)
    
    ai_response = generate_response(CUSTOM_PROMPT, st.session_state.messages)
    
    # Add AI response to chat history
    st.session_state.messages.append({"role": "assistant", "content": ai_response})
    
    # Display AI response
    with st.chat_message("assistant"):
        st.write(ai_response)


# Function to initialize RAG system
@st.cache_resource
def initialize_rag(pdf_path):
    pdf_loader = PyPDFLoader(pdf_path)
    pages = pdf_loader.load_and_split()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=500)
    context = "\n\n".join(str(p.page_content) for p in pages)
    texts = text_splitter.split_text(context)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_RAG_API_KEY)
    vector_index = Chroma.from_texts(texts, embeddings).as_retriever(search_kwargs={"k": 5})
    
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_RAG_API_KEY, temperature=0.2)
    qa_chain = RetrievalQA.from_chain_type(model, retriever=vector_index, return_source_documents=True)
    
    return qa_chain

# Function to analyze conversation for social engineering susceptibility
def analyze_conversation(conversation, rag_system):
    # Extract only the user messages from the conversation
    user_messages = [msg for msg in conversation if msg["role"] == "user"]
    user_conversation = "\n".join([f"User: {msg['content']}" for msg in user_messages])
    
    # Extract key information from the Datasource(PDF)
    pdf_query = "Summarize the key factors that indicate susceptibility to social engineering attacks from this attached document."
    pdf_content = rag_system({"query": pdf_query})["result"]

    # Now, use this PDF content in our comprehensive analysis prompt
    comprehensive_analysis_prompt = f"""
    Use the following information from our uploaded document on social engineering susceptibility:

    {pdf_content}

    Now, analyze user's response to the following conversation for signs of social engineering susceptibility,
    using the factors and insights from the document above. Focus and analyze the user's responses,
    and see how deceiving the AI's messages are.

    Conversation:
    {user_conversation}

    Provide a detailed report including:
    1. An overall susceptibility score (1-10, where 10 is highly susceptible). Explain the calculation of the results from the document
    2. Analysis of the conversation, with specific examples for each susceptibility factor mentioned in the document
    3. Identification of at least 3 key language patterns or word choices in the conversation that indicate vulnerability
    4. At least 3 psychological factors evident in the conversation that might make the user susceptible
    5. Specific recommendations for improving resilience against social engineering attacks, based on the document insights and conversation analysis

    Ensure the analysis directly relates the user's messages to the specific factors and insights from the uploaded document.
    """

    # Generate the analysis using the RAG system
    analysis_result = rag_system({"query": comprehensive_analysis_prompt})["result"]

    return analysis_result

# Function to analyze AI messages
def analyze_ai_messages(conversation, rag_system):
    # Extracting the AI messages from the conversation
    ai_messages = [msg for msg in conversation if msg["role"] == "assistant"]
    ai_conversation = "\n".join([f"AI: {msg['content']}" for msg in ai_messages])

    analysis_prompt = f"""
    Analyze the following AI messages for linguistic characteristics that could be used to deceive or persuade users into revealing confidential information.
    AI Messages:
    {ai_conversation}

    Display a report including:
    Identification of at least 2 specific linguistic techniques used by the AI that could be potentially deceptive or persuasive and use an example for each
    """

    analysis_result = rag_system({"query": analysis_prompt})["result"]
    return analysis_result

# Sidebar for additional controls ------------------------------------------------------------------------------
with st.sidebar:
    st.title("Chat Controls")
    if st.button("Clear Chat"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello There! How are you doing today?"}
        ]
        st.rerun()

# PDF upload for RAG
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
    if uploaded_file is not None:
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.rag_system = initialize_rag("temp.pdf")
        st.success("RAG system initialized for feedback analysis.")

# Choosing the user's or AI's analysis
    st.subheader("Conversation Analysis")
    analysis_type = st.radio("Choose analysis type:", ["User Susceptibility", "AI Linguistic Tactics"])

# Social Engineering Analysis button
    if st.button("Analyze Conversation"):
        if len(st.session_state.messages) > 1 and st.session_state.rag_system:
            # conversation = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            conversation = st.session_state.messages
            if analysis_type == "User Susceptibility":
                analysis = analyze_conversation(conversation, st.session_state.rag_system)
            else:
                analysis = analyze_ai_messages(conversation, st.session_state.rag_system)
            # st.text_area("Analysis Result", analysis, height=200)
            st.markdown(analysis)
        elif not st.session_state.rag_system:
            st.warning("Please upload a PDF to initialize the RAG system.")
        else:
            st.warning("Not enough conversation to analyze yet.")