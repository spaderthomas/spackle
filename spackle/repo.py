#!/usr/bin/env python

import json
import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class Repository:
    """Represents a managed repository"""
    name: str
    url: str
    path: str
    branch: str = "main"
    commit: Optional[str] = None


class RepoConfig:
    """Manages repository configuration stored in ~/.local/share/spackle/spackle.json"""
    
    def __init__(self):
        self.config_dir = os.path.expanduser("~/.local/share/spackle")
        self.config_file = os.path.join(self.config_dir, "spackle.json")
        self.cache_dir = os.path.expanduser("~/.cache/spackle/repos")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def load(self) -> List[Repository]:
        """Load repositories from config file"""
        if not os.path.exists(self.config_file):
            return []
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return [Repository(**repo) for repo in data.get('repositories', [])]
        except (json.JSONDecodeError, KeyError, TypeError):
            # If config is corrupted, start fresh
            return []
    
    def save(self, repositories: List[Repository]):
        """Save repositories to config file"""
        data = {
            'repositories': [asdict(repo) for repo in repositories]
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_repository(self, url_or_path: str, branch: Optional[str] = None) -> Repository:
        """Add a new repository, cloning if necessary"""
        repositories = self.load()
        
        # Determine if this is a URL or local path
        is_url = url_or_path.startswith(('http://', 'https://', 'git@', 'ssh://'))
        
        if is_url:
            # Extract repository name from URL
            if url_or_path.endswith('.git'):
                url_without_git = url_or_path[:-4]
            else:
                url_without_git = url_or_path
            
            # Get the last part of the URL as the name
            parts = url_without_git.rstrip('/').split('/')
            repo_name = parts[-1]
        else:
            # Local path - use the directory name
            repo_name = os.path.basename(os.path.abspath(url_or_path))
            # Convert local path to absolute path
            url_or_path = os.path.abspath(url_or_path)
        
        # Check if repository already exists
        for repo in repositories:
            if repo.name == repo_name:
                print(f"Repository '{repo_name}' already exists. Updating...")
                # Update branch if specified
                if branch:
                    repo.branch = branch
                self.save(repositories)
                self._clone_or_update_repo(repo)
                return repo
        
        # Create new repository entry
        repo_path = os.path.join(self.cache_dir, repo_name)
        new_repo = Repository(
            name=repo_name,
            url=url_or_path,
            path=repo_path,
            branch=branch or "main"
        )
        
        # Clone the repository
        self._clone_or_update_repo(new_repo)
        
        # Add to config
        repositories.append(new_repo)
        self.save(repositories)
        
        print(f"Added repository '{repo_name}' to spackle")
        return new_repo
    
    def remove_repository(self, name: str) -> bool:
        """Remove a repository from management"""
        repositories = self.load()
        
        # Find the repository
        repo_to_remove = None
        for repo in repositories:
            if repo.name == name:
                repo_to_remove = repo
                break
        
        if not repo_to_remove:
            print(f"Repository '{name}' not found")
            return False
        
        # Remove from config
        repositories = [r for r in repositories if r.name != name]
        self.save(repositories)
        
        # Remove cached directory
        if os.path.exists(repo_to_remove.path):
            shutil.rmtree(repo_to_remove.path)
            print(f"Removed cached files for '{name}'")
        
        print(f"Removed repository '{name}' from spackle")
        return True
    
    def list_repositories(self) -> List[Repository]:
        """List all managed repositories"""
        return self.load()
    
    def _clone_or_update_repo(self, repo: Repository):
        """Clone a repository or update if it exists"""
        if os.path.exists(repo.path):
            # Repository exists, fetch updates
            print(f"Updating existing repository at {repo.path}")
            try:
                # Fetch all branches
                subprocess.run(
                    ['git', 'fetch', '--all'],
                    cwd=repo.path,
                    check=True,
                    capture_output=True
                )
                # Checkout the specified branch
                subprocess.run(
                    ['git', 'checkout', repo.branch],
                    cwd=repo.path,
                    check=True,
                    capture_output=True
                )
                # Pull latest changes
                subprocess.run(
                    ['git', 'pull'],
                    cwd=repo.path,
                    check=True,
                    capture_output=True
                )
                print(f"Updated to latest {repo.branch}")
            except subprocess.CalledProcessError as e:
                print(f"Warning: Could not update repository: {e}")
        else:
            # Clone new repository
            print(f"Cloning {repo.url} to {repo.path}")
            try:
                cmd = ['git', 'clone']
                
                # Add branch flag if not main/master
                if repo.branch and repo.branch not in ['main', 'master']:
                    cmd.extend(['-b', repo.branch])
                
                cmd.extend([repo.url, repo.path])
                
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"Cloned successfully (branch: {repo.branch})")
                
                # If branch is main or master but doesn't exist, try the other
                if repo.branch in ['main', 'master']:
                    try:
                        subprocess.run(
                            ['git', 'checkout', repo.branch],
                            cwd=repo.path,
                            check=True,
                            capture_output=True
                        )
                    except subprocess.CalledProcessError:
                        # Try the alternative
                        alt_branch = 'master' if repo.branch == 'main' else 'main'
                        try:
                            subprocess.run(
                                ['git', 'checkout', alt_branch],
                                cwd=repo.path,
                                check=True,
                                capture_output=True
                            )
                            repo.branch = alt_branch
                            print(f"Note: Using branch '{alt_branch}' instead of '{repo.branch}'")
                        except subprocess.CalledProcessError:
                            pass  # Keep original branch
                
            except subprocess.CalledProcessError as e:
                print(f"Error cloning repository: {e}")
                if os.path.exists(repo.path):
                    shutil.rmtree(repo.path)
                raise
        
        # Get current commit hash
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo.path,
                check=True,
                capture_output=True,
                text=True
            )
            repo.commit = result.stdout.strip()
        except subprocess.CalledProcessError:
            repo.commit = None