from git import GitLogAnalyzer

if __name__ == "__main__":
    git_remote_url = "https://github.com/semaphore-protocol/semaphore.git"
    git_log_analyzer = GitLogAnalyzer(git_remote_url)
    git_log = git_log_analyzer.get_git_log()
    print(git_log)
    