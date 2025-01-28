import pprint
from git import GitLogAnalyzer

if __name__ == "__main__":
    git_remote_url = "https://github.com/semaphore-protocol/semaphore.git"
    git_log_analyzer = GitLogAnalyzer(git_remote_url)
    git_log = git_log_analyzer.get_git_log()
    
    commits = git_log_analyzer.split_log_by_periods(git_log, 4) # 4 weeks per period
    
    second_week_of_2024 = commits["2024-W2"]
    print(second_week_of_2024[12])