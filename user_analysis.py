import re
import csv
import os
import io
from typing import List, Dict

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