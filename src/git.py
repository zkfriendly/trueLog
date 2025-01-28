import datetime
import logging
import os
import subprocess
from typing import Dict, List

class GitLogAnalyzer:
    def __init__(self, git_remote_url: str):
        self.git_remote_url = git_remote_url
        # Create temp directory for repo
        self.repo_name = os.path.splitext(os.path.basename(git_remote_url))[0]
        self.repo_path = os.path.join("repos", self.repo_name)
        os.makedirs(self.repo_path, exist_ok=True)

        # Clone repo if it doesn't exist
        if not os.path.exists(os.path.join(self.repo_path, '.git')):
            subprocess.run(['git', 'clone', git_remote_url, self.repo_path], check=True)
        
        # Organize results by repository
        self.base_results_dir = "git_analysis_results"
        self.results_dir = os.path.join(self.base_results_dir, self.repo_name)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Setup logging with file handler
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(self.results_dir, 'analysis.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def get_git_log(self) -> str:
        """Fetch git log with detailed information"""
        self.logger.info(f"Fetching git log from {self.repo_path}")
        cmd = [
            'git',
            '-C', self.repo_path,
            'log',
            '--pretty=format:%h|%an|%ad|%s',
            '--date=iso'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout

    def split_log_by_periods(self, log_text: str, weeks_per_period: int) -> Dict[str, str]:
        """Split git log into periods of specified number of weeks
        
        Args:
            log_text: The git log text to split
            weeks_per_period: Number of weeks per period
        """
        self.logger.info(f"Splitting git log into {weeks_per_period}-week periods")
        commits = log_text.split('\n')
        periods = {}

        for commit in commits:
            if not commit.strip():
                continue

            try:
                _, _, date_str, _ = commit.split('|', 3)
                date = datetime.datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                
                # Get week number (1-52) and create period key
                week_num = date.isocalendar()[1]
                period_num = (week_num - 1) // weeks_per_period + 1
                period_key = f"{date.year}-W{period_num}"

                if period_key not in periods:
                    periods[period_key] = []
                periods[period_key].append(commit)
            except Exception as e:
                print(f"Error processing commit: {commit}")
                continue

        self.logger.info(f"Found {len(periods)} distinct periods")
        return {k: '\n'.join(v) for k, v in periods.items()}

    async def analyze_log_chunk(self, chunk: str, period: str) -> str:
        """Analyze a chunk of git log using LLM"""
        
        # Use repo name in chunk filename
        chunk_hash = hash(chunk) % 10000
        chunk_file = os.path.join(self.results_dir, f"{self.repo_name}_chunk_{period}_{chunk_hash}.txt")
        
        # Create progress tracking file
        progress_file = os.path.join(self.results_dir, f"{self.repo_name}_progress.json")
        
        # Load or initialize progress tracking
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)
        else:
            progress = {"completed_chunks": []}

        # Check if chunk was already successfully analyzed
        chunk_id = f"{period}_{chunk_hash}"
        if chunk_id in progress["completed_chunks"]:
            self.logger.info(f"Skipping already analyzed chunk {chunk_id}")
            with open(chunk_file, 'r') as f:
                return f.read()

        self.logger.info(f"Analyzing chunk for period {period} ({len(chunk)} characters)")
        prompt = f"""Analyze this section of git commit logs for period {period} and provide a brief summary of:
        1. Key changes and features
        2. Notable patterns
        
        Git logs:
        {chunk}
        """

        try:
            analysis = await self.llm_client.analyze_text(prompt)
            await asyncio.sleep(1)  # Add 1 second delay between API calls
            
            # Save chunk analysis
            with open(chunk_file, 'w') as f:
                f.write(analysis)
                
            # Mark chunk as completed and save progress
            progress["completed_chunks"].append(chunk_id)
            with open(progress_file, 'w') as f:
                json.dump(progress, f)
            
            return analysis
        except Exception as e:
            self.logger.error(f"Error analyzing chunk: {str(e)}")
            return f"Error analyzing chunk: {str(e)}"

    async def analyze_period(self, period: str, period_log: str) -> str:
        """Analyze an entire period by processing chunks and combining results"""
        chunks = self.chunk_period_log(period_log)
        self.logger.info(f"Processing period {period} - split into {len(chunks)} chunks")
        analyses = []

        # Process chunks with rate limiting
        for chunk in chunks:
            analysis = await self.analyze_chunk(chunk, period)
            analyses.append(analysis)
            await asyncio.sleep(0.5)  # Add delay between chunk processing

        self.logger.info(f"Combining analyses for period {period}")
        # Combine analyses with a more concise prompt
        combined_prompt = f"""Provide a brief, coherent summary of these git log analyses for period {period}:

        {'\n\n'.join(analyses[:5])}  # Limit number of analyses to combine
        """

        return await self.llm_client.analyze_text(combined_prompt)

    async def analyze_repository(self):
        """Main method to analyze the entire repository"""
        self.logger.info(f"Starting repository analysis for {self.repo_name}")
        
        # Use repo-specific results file
        results_file = os.path.join(self.results_dir, f'{self.repo_name}_final_results.json')
        results = {}
        if os.path.exists(results_file):
            self.logger.info("Loading existing analysis results")
            with open(results_file, 'r') as f:
                results = json.load(f)

        log_text = self.get_git_log()
        period_logs = self.split_log_by_periods(log_text)

        total_periods = len(period_logs)
        # Process periods concurrently
        tasks = []
        for i, (period, period_log) in enumerate(period_logs.items(), 1):
            if period in results:
                self.logger.info(f"Skipping already analyzed period {period}")
                continue
                
            self.logger.info(f"Analyzing period {period} ({i}/{total_periods})")
            tasks.append(self.analyze_period(period, period_log))
        
        # Wait for all period analyses to complete
        period_results = await asyncio.gather(*tasks)
        
        # Update results with new analyses
        for period, analysis in zip([p for p in period_logs.keys() if p not in results], period_results):
            results[period] = analysis
            # Save results after each period analysis
            self.logger.info(f"Saving interim results after period {period}")
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)

        self.logger.info("Repository analysis completed")
        return results
