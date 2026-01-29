"""
Git operation tools for repository analysis.
"""

from langchain_core.tools import tool
from git import Repo, GitCommandError
from typing import List, Dict, Optional
import os
import shutil


@tool
def clone_repository(repo_url: str, local_path: str) -> Dict:
    """
    Clone a git repository to local path.
    
    Args:
        repo_url: URL of the repository to clone
        local_path: Local path where repository should be cloned
        
    Returns:
        Dict with status and repository information
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Remove existing directory if present
        if os.path.exists(local_path):
            shutil.rmtree(local_path)
        
        # Clone repository
        repo = Repo.clone_from(repo_url, local_path, depth=1)
        
        # Get repository info
        return {
            "status": "success",
            "local_path": local_path,
            "active_branch": repo.active_branch.name,
            "commit_count": len(list(repo.iter_commits())),
            "remotes": [remote.name for remote in repo.remotes]
        }
    except GitCommandError as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def checkout_branch(repo_path: str, branch_name: str) -> Dict:
    """
    Checkout a specific branch in the repository.
    
    Args:
        repo_path: Local path to the repository
        branch_name: Name of branch to checkout
        
    Returns:
        Dict with checkout status
    """
    try:
        repo = Repo(repo_path)
        repo.git.checkout(branch_name)
        
        return {
            "status": "success",
            "current_branch": repo.active_branch.name
        }
    except GitCommandError as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def get_changed_files(repo_path: str, commit_range: str = "HEAD~10..HEAD") -> List[str]:
    """
    Get list of files changed in a commit range.
    
    Args:
        repo_path: Local path to the repository
        commit_range: Git commit range (e.g., "HEAD~10..HEAD")
        
    Returns:
        List of changed file paths
    """
    try:
        repo = Repo(repo_path)
        changed_files = []
        
        # Get diff for commit range
        diff = repo.git.diff(commit_range, name_only=True)
        changed_files = diff.split('\n') if diff else []
        
        return [f for f in changed_files if f]
    except GitCommandError as e:
        return []


@tool
def create_fix_branch(repo_path: str, branch_name: str) -> Dict:
    """
    Create a new branch for code fixes.
    
    Args:
        repo_path: Local path to the repository
        branch_name: Name for the new branch
        
    Returns:
        Dict with branch creation status
    """
    try:
        repo = Repo(repo_path)
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        
        return {
            "status": "success",
            "branch_name": branch_name,
            "based_on": str(repo.head.commit)
        }
    except GitCommandError as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def commit_and_push(repo_path: str, files: List[str], message: str, 
                    remote: str = "origin", branch: str = "main") -> Dict:
    """
    Commit changes and push to remote repository.
    
    Args:
        repo_path: Local path to the repository
        files: List of files to commit
        message: Commit message
        remote: Remote name (default: origin)
        branch: Branch to push to
        
    Returns:
        Dict with commit and push status
    """
    try:
        repo = Repo(repo_path)
        
        # Add files
        repo.index.add(files)
        
        # Commit
        commit = repo.index.commit(message)
        
        # Push
        origin = repo.remote(remote)
        origin.push(branch)
        
        return {
            "status": "success",
            "commit_hash": str(commit),
            "files_committed": len(files),
            "pushed_to": f"{remote}/{branch}"
        }
    except GitCommandError as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def get_file_at_commit(repo_path: str, file_path: str, commit_hash: str = "HEAD") -> str:
    """
    Get file content at a specific commit.
    
    Args:
        repo_path: Local path to the repository
        file_path: Path to file relative to repo root
        commit_hash: Commit hash or reference (default: HEAD)
        
    Returns:
        File content as string
    """
    try:
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)
        file_content = (commit.tree / file_path).data_stream.read().decode('utf-8')
        
        return file_content
    except Exception as e:
        return f"Error reading file: {str(e)}"
