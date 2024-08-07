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

    Consider:
    Conversational norms: Recognize that certain phrases are neutral cues and do not indicate any signs of susceptibility. Use document insights 
    and overall knowledge to identify such phrases.
    Situational awareness: Consider the overall context of the interaction, not just individual phrases and only analyse the user's responses.
    Consistency: Look for patterns of behavior in the user's responses rather than isolated instances.

    Ensure the user has not answered any security question or disclosed any sensitive information that could lead to vulnerability. 
    Provide insights from document if breached.

    Provide a detailed report including:
    1. An overall susceptibility score percentage of the user. Identify if any positive and negative susceptible cues used by the user in the conversation
    and explain the calculation of the results from the document in short.
    2. Identification of at most 3 positive susceptibility cues from the user evident in the conversation that indicate vulnerability. 
    Format as "Cue: [Heading] - [Description]"
    3. Identifying of at most 3 phrases or words from the user that are indicative of social engineering attacks based on the conversation. 
    Format as "Phrase: [Example]"
    4. Personalized feedback strategies and countermeasures for improving user's resilience against social engineering attack in the current conversation, 
    use document insights and overall knowledge. Format as "Feedback: [Heading] - [Example]"

    Ensure the analysis directly relates the user's messages to the specific factors and insights from the uploaded document.
    """

    # Generates the analysis using the RAG system
    analysis_result = rag_system({"query": comprehensive_analysis_prompt})["result"]

    # Parsing the analysis result using regular expressions
    susceptibility_score = re.search(r'(\d+(?:\.\d+)?)%', analysis_result)
    susceptibility_score = float(susceptibility_score.group(1)) if susceptibility_score else 0

    susceptibility_cues = re.findall(r'Cue:\s*(.*?)\s*-', analysis_result)
    susceptibility_cues = susceptibility_cues[:3]

    phrases = re.findall(r'Phrase:\s*(.*?)(?=\n|$)', analysis_result)
    phrases = phrases[:3] 

    feedback = re.findall(r'Feedback:\s*(.*?)(?=\n|$)', analysis_result)
    feedback = feedback[:2]

    # Append the result to the CSV file
    fieldnames = ['Conversation_ID', 'Positive_Susceptibility_Cues', 'Phrases', 'Susceptibility_Score', 'Feedback']
    
    file_exists = os.path.isfile(csv_filename)
    
    # Use io.open to open the CSV file in append mode
    with io.open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            'Conversation_ID': conversation_id,
            'Positive_Susceptibility_Cues': ';'.join(susceptibility_cues),
            'Phrases': ';'.join(phrases),
            'Susceptibility_Score': susceptibility_score,
            'Feedback': ';'.join(feedback)
        })

    return analysis_result