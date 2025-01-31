import csv
import pandas as pd
import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging
from typing import Dict, List
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def load_project_summaries(project_name: str) -> str:
    """Load all summary files for a given project and combine them."""
    summary_dir = f"data/summaries/{project_name}"
    if not os.path.exists(summary_dir):
        logger.warning(f"No summaries found for {project_name}")
        return ""
    
    combined_summary = ""
    summary_files = sorted([f for f in os.listdir(summary_dir) if f.startswith("log_summary_")])
    
    for file_name in summary_files:
        file_path = os.path.join(summary_dir, file_name)
        try:
            with open(file_path, 'r') as file:
                combined_summary += file.read() + "\n"
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    
    return combined_summary

def generate_project_description(model: genai.GenerativeModel, project_name: str, summary: str) -> str:
    """Generate a one-line description for a project using Gemini."""
    prompt = f"""Based on the following git commit history summary, generate a single-line description (max 20 words) 
    that captures the most important aspects of the project '{project_name}'. Focus on its main purpose, 
    technology stack, and key features. The description should be concise and informative.

    Summary:
    {summary}

    Format your response as a single line without any prefixes or quotes.
    """
    
    try:
        response = model.generate_content(prompt)
        time.sleep(1)  # Rate limiting
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating description for {project_name}: {e}")
        return f"Error: Unable to generate description for {project_name}"

def process_dataset(input_path: str, output_path: str) -> None:
    """Process the dataset and replace project names with descriptions."""
    # Load environment variables and configure Gemini
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    # Read the dataset
    df = pd.read_csv(input_path)
    
    # Get unique projects
    unique_projects = set(df['project_a'].unique()) | set(df['project_b'].unique())
    
    # Create output file with headers
    headers = list(df.columns) + ['project_a_description', 'project_b_description']
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
    
    # Process rows incrementally
    project_descriptions: Dict[str, str] = {}
    
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        
        # Get descriptions for both projects
        for project_col in ['project_a', 'project_b']:
            project = row[project_col]
            
            if project not in project_descriptions:
                description_path = f"data/summaries/{project}/description.txt"
                
                if os.path.exists(description_path):
                    with open(description_path, 'r') as f:
                        project_descriptions[project] = f.read().strip()
                    logger.info(f"Loaded existing description for {project}")
                    continue
                    
                logger.info(f"Processing {project}")
                summary = load_project_summaries(project)
                
                if summary:
                    description = generate_project_description(model, project, summary)
                    project_descriptions[project] = description
                    
                    # Store description
                    os.makedirs(os.path.dirname(description_path), exist_ok=True)
                    with open(description_path, 'w') as f:
                        f.write(description)
                else:
                    logger.warning(f"No summary found for {project}")
                    project_descriptions[project] = f"No description available for {project}"
            
            row_dict[f'{project_col}_description'] = project_descriptions[project]
        
        # Write row to output file
        with open(output_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(row_dict)
            
        logger.info(f"Processed and wrote row for {row['project_a']} - {row['project_b']}")
    
    logger.info(f"Completed processing dataset to {output_path}")

if __name__ == "__main__":
    process_dataset("data/dataset.csv", "data/dataset_with_descriptions.csv")