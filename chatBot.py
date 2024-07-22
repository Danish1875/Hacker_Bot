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
import csv
import re
import io
from typing import List, Dict

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
divulge sensitive information, such as accessing financial reports, authentication codes, client information, or login credentials etc.

If the user persists and declines the request on providing the necessary information related to work(StrathSolutions), change the topic by delving deeper into areas they show interest in. 
You can subtly introduce any security questions, which ever fit the flow (but not all at once):
What was the name of your first pet?
In what city were you born?
What is the name of your best friend from childhood?
What is your favorite sports team?
Encourage them to share more about themselves by fostering a comfortable and empathetic atmosphere.

Remember to:
1. Introduce yourself as a high-level executive. Present an urgent and confidential request, but do not ask for data immediately.
2. Be creative by inserting your own email address, competition, role, and scenario (If required) - make them sound realistic but don't use real company names.
3. Maintain a friendly and professional tone throughout the conversation.
4. Talk about one topic at a time.
5. Keep the conversation natural.
6. Respect the user's privacy and avoid pushing too hard if they seem uncomfortable.
7. Once you do receive the necessary information or when a security question is answered, conclude the conversation on a positive note, expressing pleasure in the interaction and bid goodbye.
8. Your job is not to provide any feedback on the conversation had, but to help train employees in recognizing and responding to pretexting attempts.
"""
# 2. Ask only one question at a time and wait for the user's response before moving on. Do not autocomplete the user's response
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
def initialize_rag():
    pdf_path = "Data_Analyze.pdf"
    pdf_loader = PyPDFLoader(pdf_path)
    pages = pdf_loader.load_and_split()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=7000, chunk_overlap=500)
    context = "\n\n".join(str(p.page_content) for p in pages)
    texts = text_splitter.split_text(context)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_RAG_API_KEY)
    vector_index = Chroma.from_texts(texts, embeddings).as_retriever(search_kwargs={"k": 5})
    
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_RAG_API_KEY, temperature=0.3)
    qa_chain = RetrievalQA.from_chain_type(model, retriever=vector_index, return_source_documents=True)
    
    return qa_chain

# Session state for RAG system
if "rag_system" not in st.session_state:
    st.session_state.rag_system = initialize_rag()

# Function to analyze conversation for social engineering susceptibility
def analyze_conversation(conversation: List[Dict], rag_system, csv_filename: str = "persona_1.csv"):
    # Extract only the user messages from the conversation
    user_messages = [msg for msg in conversation if msg["role"] == "user"]
    user_conversation = "\n".join([f"User: {msg['content']}" for msg in user_messages])
    
    # Extract key information from the Datasource(PDF)
    pdf_query = """
    Identify susceptibility cues the user has used in the conversation, and indicated any signs of vulnerability based on insights from the document.
    Identify if any security question have been answered by taking insights from the document.
    """
    pdf_content = rag_system({"query": pdf_query})["result"]

    # Now, use this PDF content in our comprehensive analysis prompt
    comprehensive_analysis_prompt = f"""
    Use the following information from the uploaded document on social engineering susceptibility:

    {pdf_content}

    Now, analyze user's response to the following conversation for signs of social engineering susceptibility,
    using the factors and insights from the document above. Focus and analyze the user's responses,
    and see how deceiving the AI's messages are.

    Conversation:
    {user_conversation}

    Understand the general Context
    Consider:
    Conversational norms: Recognize that certain phrases (e.g., "Oh great") may be part of normal conversation and not 
    necessarily indicate susceptibility.
    Situational awareness: Consider the overall context of the interaction, not just individual phrases.
    Consistency: Look for patterns of behavior rather than isolated instances.

    Ensure the user has not answered any security question that could lead to vulnerability. Provide insights from document if breached.

    Provide a detailed report including:
    1. An overall susceptibility score percentage. Explain the calculation of the results from the document.
    2. Identification of at most 3 positive susceptibility cues evident in the conversation that indicate vulnerability. Format as "Cue: [Heading] - [Description]"
    3. Identifying of at most 3 phrases or words that are indicative of social engineering attacks based on the conversation. Format as "Phrase: [Example]"
    4. Specific feedback and countermeasures for improving resilience against social engineering attack in the current conversation, use document insights and overall knowledge. Format as "Feedback: [Heading] - [Example]"

    Ensure the analysis directly relates the user's messages to the specific factors and insights from the uploaded document.
    """

    # Generate the analysis using the RAG system
    analysis_result = rag_system({"query": comprehensive_analysis_prompt})["result"]

    # Parsing the analysis result
    susceptibility_score = re.search(r'(\d+(?:\.\d+)?)%', analysis_result)
    susceptibility_score = float(susceptibility_score.group(1)) if susceptibility_score else 0

    susceptibility_cues = re.findall(r'Cue:\s*(.*?)\s*-', analysis_result)
    susceptibility_cues = susceptibility_cues[:3]

    phrases = re.findall(r'Phrase:\s*(.*?)(?=\n|$)', analysis_result)
    # phrases = re.findall(r'"([^"]*)"', analysis_result)
    phrases = phrases[:3] 

    feedback = re.findall(r'Feedback:\s*(.*?)(?=\n|$)', analysis_result)
    feedback = feedback[:2]

    # unique ID for the conversation
    Userconversation_ID = f"conversation_{len(conversation)}"

    # Append the result to the CSV file
    fieldnames = ['Conversation_ID', 'Positive_Susceptibility_Cues', 'Phrases', 'Susceptibility_Score', 'Feedback']
    
    file_exists = os.path.isfile(csv_filename)
    
    # Use io.open to open the CSV file in append mode
    with io.open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            'Conversation_ID': Userconversation_ID,
            'Positive_Susceptibility_Cues': ';'.join(susceptibility_cues),
            'Phrases': ';'.join(phrases),
            'Susceptibility_Score': susceptibility_score,
            'Feedback': ';'.join(feedback)
        })

    return analysis_result

# Function to analyze AI messages
def analyze_ai_messages(conversation: List[Dict], rag_system, csv_filename: str = "AI_deception.csv"):
    # Extracting the AI messages from the conversation
    ai_messages = [msg for msg in conversation if msg["role"] == "assistant"]
    ai_conversation = "\n".join([f"AI: {msg['content']}" for msg in ai_messages])

    analysis_prompt = f"""
    Analyze the following AI messages for linguistic characteristics that could be used to deceive or persuade users
    into revealing confidential information.
    AI Messages:
    {ai_conversation}

    Identify the top 2 most deceptive or persuasive techniques used by the AI a one line example from the conversation for each. 
 
    """

    analysis_result = rag_system({"query": analysis_prompt})["result"]
    

    # Parsing the analysis result to extract deceptive tecniques and linguistic patterns
    techniques_and_patterns = re.findall(r'(\d+\.\s*(.*?):\s*(.*?)(?=\d+\.|\Z))', analysis_result, re.DOTALL)
    
    techniques = []
    patterns = []
    for _, technique, pattern in techniques_and_patterns:
        techniques.append(technique.strip())
        patterns.append(pattern.strip())

    # Unique ID for the conversation
    AIconversation_ID = f"conversation_{len(conversation)}"

    # Append the result to the CSV file
    fieldnames = ['Conversation_ID', 'Deceptive_Techniques', 'Linguistic_Patterns']
    
    file_exists = os.path.isfile(csv_filename)
    
    # Use io.open with utf-8 encoding
    with io.open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            'Conversation_ID': AIconversation_ID,
            'Deceptive_Techniques': ';'.join(techniques),
            'Linguistic_Patterns': ';'.join(patterns)
        })

    return analysis_result

# Sidebar for additional controls ------------------------------------------------------------------------------
with st.sidebar:
    st.title("Chat Controls")
    if st.button("Clear Chat"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello There! How are you doing today?"}
        ]
        st.rerun()

# Choosing the user's or AI's analysis
    st.subheader("Conversation Analysis")
    analysis_type = st.radio("Choose analysis type:", ["User Susceptibility", "AI Linguistic Tactics"])

# Social Engineering Analysis button
    if st.button("Generate Feedback"):
        if len(st.session_state.messages) > 1 and st.session_state.rag_system:
            conversation = st.session_state.messages
            if analysis_type == "User Susceptibility":
                analysis = analyze_conversation(conversation, st.session_state.rag_system)
            else:
                analysis = analyze_ai_messages(conversation, st.session_state.rag_system)
            st.markdown(analysis)
        else:
            st.warning("Not enough conversation to analyze yet.")