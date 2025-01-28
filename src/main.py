import asyncio
import subprocess
import datetime
from openai import AsyncOpenAI
import logging
from typing import List, Dict, Protocol
import json
from dotenv import load_dotenv
import os
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

# Load environment variables from .env file
load_dotenv()

class LLMClient(Protocol):
    async def analyze_text(self, prompts: List[str]) -> List[str]:
        """Analyze multiple texts using LLM and return responses"""
        pass

class OpenAIClient:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_text(self, prompts: List[str]) -> List[str]:
        # Create batch of messages
        messages_batch = [
            [
                {"role": "system", "content": "You are a git log analyzer. Provide very concise summaries."},
                {"role": "user", "content": prompt}
            ]
            for prompt in prompts
        ]
        
        # Make a single API call for the batch
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=messages_batch,
            max_tokens=1000
        )
        
        # Extract all responses
        return [choice.message.content for choice in response.choices]

# Usage example
if __name__ == "__main__":
    import tempfile
    import subprocess
    import json
    import os.path

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Load repos from json file
    try:
        with open('data/repos.json', 'r') as f:
            repos = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError("repos.json file not found")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in repos.json")

    # Process repositories in batches
    BATCH_SIZE = 5  # Adjust based on your needs

    async def process_repos_batch(repo_urls: List[str], api_key: str):
        tasks = []
        temp_dirs = []
        
        # Setup all repos in parallel
        for repo_url in repo_urls:
            # Extract repo name from URL
            repo_name = os.path.basename(repo_url.rstrip('/'))
            
            # Create temp dir with repo name
            temp_dir = os.path.join(tempfile.gettempdir(), repo_name)
            temp_dirs.append(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            
            print(f"Processing repository: {repo_url}")
            
            # Only clone if repo doesn't already exist
            if not os.path.exists(os.path.join(temp_dir, '.git')):
                tasks.append(asyncio.create_task(
                    asyncio.to_thread(
                        subprocess.run,
                        ['git', 'clone', repo_url, temp_dir],
                        check=True
                    )
                ))
        
        # Wait for all clones to complete
        if tasks:
            await asyncio.gather(*tasks)
        
        # Create single LLM client for batch
        llm_client = OpenAIClient(api_key)
        
        # Collect all prompts from repos
        all_prompts = []
        for temp_dir in temp_dirs:
            analyzer = GitLogAnalyzer(temp_dir, llm_client)
            prompts = await analyzer.collect_prompts()  # You'll need to modify GitLogAnalyzer to have this method
            all_prompts.extend(prompts)
        
        # Process prompts in batches
        results = []
        for i in range(0, len(all_prompts), BATCH_SIZE):
            batch = all_prompts[i:i + BATCH_SIZE]
            batch_results = await llm_client.analyze_text(batch)
            results.extend(batch_results)
        
        # Save results for each repo
        result_idx = 0
        for temp_dir in temp_dirs:
            analyzer = GitLogAnalyzer(temp_dir, llm_client)
            num_prompts = len(await analyzer.collect_prompts())
            repo_results = results[result_idx:result_idx + num_prompts]
            result_idx += num_prompts
            
            final_results_file = os.path.join(analyzer.results_dir, f'{analyzer.repo_name}_final_results.json')
            with open(final_results_file, 'w') as f:
                json.dump(repo_results, f, indent=2)

    async def main():
        # Process repos in batches
        for i in range(0, len(repos), BATCH_SIZE):
            batch = repos[i:i + BATCH_SIZE]
            await process_repos_batch(batch, api_key)

    asyncio.run(main())