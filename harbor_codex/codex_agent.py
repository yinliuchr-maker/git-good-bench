"""
Codex Agent Implementation for GitGoodBench

This module provides a Codex agent that can solve GitGoodBench tasks
using the OpenAI code-davinci-002 model through the Harbor framework.
"""

import os
import json
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path


class CodexAgent:
    """
    Codex Agent for GitGoodBench tasks.
    
    Integrates OpenAI's Codex (code-davinci-002) with the GitGoodBench benchmark
    to evaluate code generation and git command execution capabilities.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Codex Agent.
        
        Args:
            api_key: OpenAI API key. If not provided, will use OPENAI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. "
                "Please provide it via api_key parameter or OPENAI_API_KEY environment variable."
            )
        
        self.model = "code-davinci-002"
        self.api_endpoint = "https://api.openai.com/v1/completions"
    
    def solve_merge_task(self, task_description: str, repo_path: str) -> bool:
        """
        Solve a merge conflict resolution task.
        
        Args:
            task_description: Description of the merge conflict task
            repo_path: Path to the git repository
            
        Returns:
            True if the task was solved successfully, False otherwise
        """
        prompt = self._build_merge_prompt(task_description, repo_path)
        commands = self._get_codex_response(prompt)
        
        if not commands:
            return False
        
        return self._execute_commands(commands, repo_path)
    
    def solve_file_commit_chain_task(self, task_description: str, repo_path: str) -> bool:
        """
        Solve a file commit chain task.
        
        Args:
            task_description: Description of the file commit chain task
            repo_path: Path to the git repository
            
        Returns:
            True if the task was solved successfully, False otherwise
        """
        prompt = self._build_file_chain_prompt(task_description, repo_path)
        commands = self._get_codex_response(prompt)
        
        if not commands:
            return False
        
        return self._execute_commands(commands, repo_path)
    
    def _build_merge_prompt(self, task_description: str, repo_path: str) -> str:
        """Build a prompt for merge conflict resolution."""
        return f"""
You are an expert Git user solving merge conflict resolution tasks.

Task Description:
{task_description}

Repository: {repo_path}

Instructions:
1. Analyze the merge conflict
2. Generate appropriate git commands to resolve it
3. Ensure the final state matches the target commit

Provide ONLY the git commands (one per line, without bash prompt markers):
"""
    
    def _build_file_chain_prompt(self, task_description: str, repo_path: str) -> str:
        """Build a prompt for file commit chain tasks."""
        return f"""
You are an expert Git user solving file commit chain manipulation tasks.

Task Description:
{task_description}

Repository: {repo_path}

Instructions:
1. Understand the target file state
2. Generate git commands to achieve it
3. Manipulate commits and file history as needed
4. Ensure the final file matches the target state

Provide ONLY the git commands (one per line, without bash prompt markers):
"""
    
    def _get_codex_response(self, prompt: str) -> list:
        """
        Get response from Codex API.
        
        Args:
            prompt: The prompt to send to Codex
            
        Returns:
            List of git commands to execute
        """
        try:
            # Note: This is a placeholder for actual API call
            # In production, use OpenAI SDK: from openai import OpenAI
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "prompt": prompt,
                "temperature": 0.5,
                "max_tokens": 500,
                "stop": ["\n\n"]
            }
            
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Codex API error: {response.status_code}")
                return []
            
            result = response.json()
            if "choices" not in result or not result["choices"]:
                return []
            
            text = result["choices"][0].get("text", "").strip()
            commands = [cmd.strip() for cmd in text.split('\n') if cmd.strip()]
            
            return commands
            
        except Exception as e:
            print(f"Error calling Codex API: {e}")
            return []
    
    def _execute_commands(self, commands: list, repo_path: str) -> bool:
        """
        Execute git commands in the repository.
        
        Args:
            commands: List of git commands to execute
            repo_path: Path to the git repository
            
        Returns:
            True if all commands executed successfully, False otherwise
        """
        try:
            for cmd in commands:
                # Ensure it's a valid git command
                if not cmd.startswith('git '):
                    cmd = f"git {cmd}"
                
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    print(f"Command failed: {cmd}")
                    print(f"Error: {result.stderr}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error executing commands: {e}")
            return False


def main():
    """Example usage of CodexAgent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Codex Agent for GitGoodBench")
    parser.add_argument("--task-file", type=str, help="Path to task JSON file")
    parser.add_argument("--repo-path", type=str, help="Path to git repository")
    parser.add_argument("--task-type", type=str, choices=["merge", "file_chain"], 
                       help="Type of task to solve")
    
    args = parser.parse_args()
    
    # Initialize agent
    agent = CodexAgent()
    
    # Load task
    if args.task_file:
        with open(args.task_file, 'r') as f:
            task = json.load(f)
    
    # Solve task
    if args.task_type == "merge":
        result = agent.solve_merge_task(task.get('description', ''), args.repo_path)
    else:
        result = agent.solve_file_commit_chain_task(task.get('description', ''), args.repo_path)
    
    print(f"Task solved: {result}")
    return 0 if result else 1


if __name__ == "__main__":
    main()
