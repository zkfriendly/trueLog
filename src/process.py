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

def process_dataset(input_path: str, output_path: str) -> None:
    """Process the dataset and replace project names with descriptions."""
    # Load environment variables and configure Gemini
    load_dotenv()
    
    # Read the dataset
    df = pd.read_csv(input_path)
    
    # Create output file with headers
    headers = ['project_a', 'project_b', 'weight_a', 'weight_b']
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
    
    # Process rows incrementally
    project_descriptions: Dict[str, str] = {}
    
    for _, row in df.iterrows():
        row_dict = {
            'weight_a': row['weight_a'],
            'weight_b': row['weight_b']
        }
        
        # Get descriptions for both projects
        for project_col in ['project_a', 'project_b']:
            project = row[project_col]
            
            if project not in project_descriptions:
                description_path = f"data/summaries/{project}/description.txt"
                
                with open(description_path, 'r') as f:
                    project_descriptions[project] = f.read().strip()
            
            row_dict[project_col] = project_descriptions[project]
        
        # Write row to output file
        with open(output_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writerow(row_dict)
            
        logger.info(f"Processed and wrote row for {row['project_a']} - {row['project_b']}")
    
    logger.info(f"Completed processing dataset to {output_path}")

if __name__ == "__main__":
    process_dataset("data/dataset.csv", "data/dataset_with_descriptions.csv")