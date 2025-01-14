# push_to_repository.py
import os
from git import Repo
import csv
import pytz
from datetime import datetime

# File paths
LOCAL_LOG_PATH = "/path/to/local_owl_log.csv"  # Replace with actual path
REPO_PATH = "/path/to/git/repo"  # Replace with actual path to your GitHub repository
REPO_LOG_PATH = os.path.join(REPO_PATH, "30_Logs/repository_owl_log.csv")

# Function to append local log to repository log
def merge_logs():
    if not os.path.exists(LOCAL_LOG_PATH):
        print(f"Local log file not found: {LOCAL_LOG_PATH}")
        return

    # Ensure repository log exists
    if not os.path.exists(REPO_LOG_PATH):
        with open(REPO_LOG_PATH, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "OwlInBox", "OwlOnBox", "OwlInArea", "TotalOwls"])

    # Append content from local to repository log
    with open(REPO_LOG_PATH, "a", newline="") as repo_file, open(LOCAL_LOG_PATH, "r") as local_file:
        repo_writer = csv.writer(repo_file)
        local_reader = csv.reader(local_file)
        next(local_reader)  # Skip header
        for row in local_reader:
            repo_writer.writerow(row)

    print(f"Logs merged into {REPO_LOG_PATH}")

# Function to push changes to GitHub
def push_to_git():
    repo = Repo(REPO_PATH)
    repo.git.add(update=True)
    repo.index.commit(f"Update logs on {datetime.now(pytz.timezone('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S')}")
    origin = repo.remote(name="origin")
    origin.push()
    print("Changes pushed to GitHub")

if __name__ == "__main__":
    merge_logs()
    push_to_git()
