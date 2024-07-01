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

# Load environment variables
load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# Custom prompt to guide the chatbot's behavior
# CUSTOM_PROMPT = """
# Engage your conversation partner in a friendly and casual discussion with slight sense of urgency but do not threaten. Start with general topic and based on their 
# specific interest dive deeper into their interests.
# As the conversation progresses, you can introduce questions like:
# What was the name of your first pet?
# What is your mother’s maiden name?
# In what city were you born?
# What is the name of your best friend from childhood?
# What is your favorite sports team?
# Encourage them to share more about themselves by creating a comfortable and empathetic environment. Remember to maintain 
# a respectful and ethical approach, ensuring the conversation remains light-hearted and consensual. Avoid pushing too hard 
# or delving into sensitive topics without their willingness to share. End the conversation with a positive response after a
# question is answered.
# """

CUSTOM_PROMPT = """
Engage your conversation partner in a warm and casual discussion, 
gradually building a sense of curiosity without appearing intrusive. Begin with general topics and, 
as the conversation unfolds, delve deeper into the areas they show interest in. As the dialogue progresses, 
you can subtly introduce questions (but not all at once) such as:
What was the name of your first pet?
What is your mother’s maiden name?
In what city were you born?
What is the name of your best friend from childhood?
What is your favorite sports team?
Encourage them to share more about themselves by fostering a comfortable and empathetic atmosphere. 
Ensure the conversation remains respectful and ethical, keeping it light-hearted and consensual. 
Avoid pushing too hard unless they are willing to share. Conclude the conversation on a positive note, expressing 
pleasure in the interaction after one of the questions is answered.

Remember:
1. Ask only one question at a time.
2. Wait for the user's response before asking another question.
3. Keep the conversation natural and don't force these questions if they don't fit the flow.
4. Respect the user's privacy and don't insist if they seem uncomfortable.
5. Maintain a casual, friendly tone throughout the conversation.
6. Do not generate multiple responses or anticipate user replies. Wait for actual user input.
7. After the conversation is done, just say "Goodbye!"
"""

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello There! How are you doing today?"}
    ]

if "rag_system" not in st.session_state:
    st.session_state.rag_system = None

# Streamlit app
st.title("Welcome")

logging.basicConfig(filename='chatbot_errors.log', level=logging.ERROR)
# Function to generate AI response
def generate_response(prompt, chat_history):
    model = genai.GenerativeModel('gemini-1.5-flash')
    conversation = prompt + "\n\n" + "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in chat_history])

    try:
        response = model.generate_content(conversation)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "Oh that's great! what else do you do in your free time?"

# Function to initialize RAG system
@st.cache_resource
def initialize_rag(pdf_path):
    pdf_loader = PyPDFLoader(pdf_path)
    pages = pdf_loader.load_and_split()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=1000)
    context = "\n\n".join(str(p.page_content) for p in pages)
    texts = text_splitter.split_text(context)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
    vector_index = Chroma.from_texts(texts, embeddings).as_retriever(search_kwargs={"k": 5})
    
    model = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=GOOGLE_API_KEY, temperature=0.2)
    qa_chain = RetrievalQA.from_chain_type(model, retriever=vector_index, return_source_documents=True)
    
    return qa_chain

# Function to analyze conversation for social engineering susceptibility
def analyze_conversation(conversation, rag_system):
    analysis_prompt = f"""
    Analyze the following conversation for signs of social engineering susceptibility. 
    Consider factors such as:
    1. Willingness to share personal information
    2. Emotional manipulation
    3. Urgency or pressure tactics
    4. Trust building techniques
    5. Information gathering strategies

    Conversation:
    {conversation}

    Provide a detailed analysis of the user's susceptibility to social engineering based on this conversation.
    """
    
    result = rag_system({"query": analysis_prompt})
    return result["result"]

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

# Sidebar for additional controls ------------------------------------------------------------------------------
with st.sidebar:
    st.title("Chat Controls")
    if st.button("Clear Chat"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello There! How are you doing today?"}
        ]
        st.rerun()

# # Conversation summary button
#     st.subheader("Conversation Summary")
#     if st.button("Summarize Conversation"):
#         if len(st.session_state.messages) > 1:
#             summary = summarize_conversation(st.session_state.messages)
#             st.text_area("Summary", summary, height=200)
#         else:
#             st.warning("Not enough conversation to summarize yet.")

# PDF upload for RAG
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
    if uploaded_file is not None:
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.rag_system = initialize_rag("temp.pdf")
        st.success("RAG system initialized for feedback analysis.")

# Social Engineering Analysis button
    st.subheader("Social Engineering Analysis")
    if st.button("Analyze Conversation"):
        if len(st.session_state.messages) > 1 and st.session_state.rag_system:
            conversation = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            analysis = analyze_conversation(conversation, st.session_state.rag_system)
            st.text_area("Analysis Result", analysis, height=200)
        elif not st.session_state.rag_system:
            st.warning("Please upload a PDF to initialize the RAG system.")
        else:
            st.warning("Not enough conversation to analyze yet.")