import logging
from dotenv import load_dotenv
import os
import time
import google.generativeai as genai
import json

from git import GitLogAnalyzer

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s - %(levelname)s - %(message)s", 
    handlers=[
        logging.StreamHandler(),  
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

if __name__ == "__main__":
    # Load the list of GitHub repositories from the JSON file
    with open('data/repos.json', 'r') as json_file:
        repos_data = json.load(json_file)
        repositories = repos_data['repositories']  # Assuming the key is 'repositories'

    total_repos = len(repositories)  # Total number of repositories
    logger.info(f"Starting processing {total_repos} repositories.")

    for index, git_remote_url in enumerate(repositories, start=1):
        logger.info(f"Processing repository {index}/{total_repos}: {git_remote_url}")
        
        git_log_analyzer = GitLogAnalyzer(git_remote_url)
        repo_name = git_remote_url.split("/")[-1]  # Extract repository name from URL
        logger.info(f"Processing repository: {repo_name}")
        
        git_log = git_log_analyzer.get_git_log()
        commits = git_log_analyzer.split_log_by_max_token_size(git_log, 400000)


        # Create a directory for the repository if it doesn't exist
        os.makedirs(f"data/summaries/{repo_name}", exist_ok=True)  # Create directory

        # Configure the model
        model = genai.GenerativeModel('gemini-1.5-pro')
        for period, commit_log in enumerate(commits):
            # Check if file already exists
            file_name = f"data/summaries/{repo_name}/log_summary_{period}.txt"
            if os.path.exists(file_name):
                logger.info(f"Skipping period {period} - file already exists")
                continue

            
            prompt = git_log_analyzer.analyze_log_chunk_promt(commit_log, "")
            logger.info(f"Waiting for Gemini...")

            time.sleep(2)

            # Generate response using Gemini
            response = model.generate_content(prompt)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_name), exist_ok=True)
            
            # Create a new text file for each response
            with open(file_name, "w") as file:
                file.write(response.text)  # Changed to access response text

        logger.info(f"Finished processing repository {index}/{total_repos}: {git_remote_url}")

    logger.info("All repositories have been processed successfully.")
    