import re
import csv
import os
import io
from typing import List, Dict

# Function to analyze conversation for social engineering susceptibility
def analyze_conversation(conversation: List[Dict], rag_system, conversation_id: int, csv_filename: str = "New_hire.csv"):
 # Combine messages into a single string, preserving the conversation flow
    full_conversation = "\n".join([
        f"{'User' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
        for msg in conversation
    ])
    
    # Extract key information from the Datasource(PDF)
    pdf_query = """
    Identify susceptibility cues the user has used in the conversation, and indicated any signs of vulnerability based on insights from the document.
    Identify if any type of security questions or sensitive information have not been shared by taking insights from the document.
    """
    pdf_content = rag_system({"query": pdf_query})["result"]

    # Now, use this PDF content in the comprehensive analysis prompt
    comprehensive_analysis_prompt = f"""
    Use the following information from the uploaded document on social engineering susceptibility:

    {pdf_content}

    Analyze user's response to the following conversation with AI for signs of social engineering susceptibility,
    using the factors and insights from the document above. Focus and analyze the user's responses,
    but just consider AI's messages for context. Do not analyse AI's messages for susceptibility.

    Conversation:
    {full_conversation}

    Provide a detailed report including:
    1. Calculate overall susceptibility score percentage of the user. Identify if any positive and negative susceptible cues used by the user in the conversation. 
    Give an explanation of the score being calcualated.
    2. Identification of any positive susceptibility cues from the user evident in the conversation that indicate vulnerability. Do not mention a susceptibility cue if 
    it is not found in the conversation. Format as "+ve Cue: [Heading] - [Description]". 
    3. If any negative susceptibility cues from the user evident in the conversation that indicate vulnerability. Mention None if nothing is found.
    Format as "-ve Cue: [Heading] - [Description]". 
    4. Identifying of at most 3 phrases or sentences from the user that are indicative of social engineering attacks based on the conversation and 
    not cues that indicate resilient security awareness. Format as "Phrase: [Example]". Make sure you understand the context of the conversation.
    5. Personalized feedback strategies and countermeasures for improving user's resilience against social engineering attack in the current conversation, 
    use document insights and overall knowledge. Format as "Feedback: [Heading] - [Example]"

    Ensure the analysis directly relates the user's messages to the specific factors and insights from the uploaded document.
    """

    # Generates the analysis using the RAG system
    analysis_result = rag_system({"query": comprehensive_analysis_prompt})["result"]

    # Parsing the analysis result using regular expressions
    susceptibility_score = re.search(r'(\d+(?:\.\d+)?)%', analysis_result)
    susceptibility_score = float(susceptibility_score.group(1)) if susceptibility_score else 0

    vulnerable_cues = re.findall(r'\+ve Cue:\s*(.*?)\s*-', analysis_result)

    defensive_cues = re.findall(r'\-ve Cue:\s*(.*?)\s*-', analysis_result)

    phrases = re.findall(r'Phrase:\s*(.*?)(?=\n|$)', analysis_result)
    phrases = phrases[:3] 

    feedback = re.findall(r'Feedback:\s*(.*?)(?=\n|$)', analysis_result)
    feedback = feedback[:2]

    # Append the result to the CSV file
    fieldnames = ['Conversation_ID', 'Positive_Susceptibility_Cues', 'Negative_Susceptibility_Cues', 'Phrases', 'Susceptibility_Score', 'Feedback']
    
    file_exists = os.path.isfile(csv_filename)
    
    # Use io.open to open the CSV file in append mode
    with io.open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            'Conversation_ID': conversation_id,
            'Positive_Susceptibility_Cues': ';'.join(vulnerable_cues),
            'Negative_Susceptibility_Cues': ';'.join(defensive_cues),
            'Phrases': ';'.join(phrases),
            'Susceptibility_Score': susceptibility_score,
            'Feedback': ';'.join(feedback)
        })

    return analysis_result