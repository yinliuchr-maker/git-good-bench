"""
Run Codex CLI on GitGoodBench tasks for parity experiments.

Usage:
    export OPENAI_API_KEY=<key>
    python run_codex_benchmark.py --num-tasks 120 --output results.json
"""

import os
import sys
import json
import subprocess
import shutil
import ast
import time
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from datasets import load_dataset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task_id: str
    sample_type: str
    success: bool
    execution_time_sec: float
    error: str = None


class CodexBenchRunner:
    def __init__(self, work_dir="./codex_workdir"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Loading dataset from HuggingFace...")
        self.dataset = load_dataset("JetBrains/git_good_bench-lite", split="train")
        logger.info(f"Loaded {len(self.dataset)} tasks")

    def setup_task(self, task):
        task_id = task['id']
        repo_name = task['name']
        scenario = ast.literal_eval(task['scenario']) if isinstance(task['scenario'], str) else task['scenario']
        sample_type = task['sample_type']

        task_dir = self.work_dir / task_id.lower().replace('/', '_')
        if task_dir.exists():
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True)
        repo_dir = task_dir / "repo"

        clone_url = f"https://github.com/{repo_name}.git"
        result = subprocess.run(
            ["git", "clone", "--depth", "100", clone_url, str(repo_dir)],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone {repo_name}: {result.stderr}")

        subprocess.run(["git", "config", "user.email", "codex@test.com"], cwd=repo_dir)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=repo_dir)

        if sample_type == "merge":
            parents = scenario.get('parents', [])
            if len(parents) >= 2:
                subprocess.run(["git", "fetch", "origin", parents[0]], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "checkout", parents[0]], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "fetch", "origin", parents[1]], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "merge", parents[1], "--no-commit"], cwd=repo_dir, capture_output=True)
        elif sample_type == "file_commit_chain":
            oldest = scenario.get('oldest_commit')
            if oldest:
                subprocess.run(["git", "fetch", "origin", oldest], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "checkout", oldest], cwd=repo_dir, capture_output=True)

        return repo_dir

    def build_prompt(self, task):
        scenario = ast.literal_eval(task['scenario']) if isinstance(task['scenario'], str) else task['scenario']
        sample_type = task['sample_type']

        if sample_type == "merge":
            return f"""Resolve the merge conflict in this git repository.

Target commit: {scenario.get('merge_commit_hash', 'N/A')}
Files with conflicts: {scenario.get('files_in_merge_conflict', 'N/A')}

Steps:
1. Check git status and git diff
2. Resolve all conflicts
3. Stage files with git add
4. Complete the merge"""

        elif sample_type == "file_commit_chain":
            return f"""Update the target file to match the expected state.

Target file: {scenario.get('file', 'N/A')}
Target commit: {scenario.get('newest_commit', 'N/A')}

Use git commands to get the file content from the target commit."""

        return "Unknown task"

    def run_codex(self, repo_dir, prompt, timeout=600):
        try:
            env = {**os.environ}
            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CODEX_API_KEY")
            if api_key:
                env["CODEX_API_KEY"] = api_key

            result = subprocess.run(
                ["codex", "exec", "--full-auto", "--sandbox", "workspace-write", prompt],
                cwd=repo_dir, capture_output=True, text=True, timeout=timeout, env=env
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout after {timeout}s")
            return False
        except FileNotFoundError:
            logger.error("Codex CLI not found. Install: npm i -g @openai/codex")
            return False
        except Exception as e:
            logger.error(f"Error: {e}")
            return False

    def evaluate(self, task, repo_dir):
        scenario = ast.literal_eval(task['scenario']) if isinstance(task['scenario'], str) else task['scenario']
        sample_type = task['sample_type']

        try:
            if sample_type == "merge":
                expected_hash = scenario.get('merge_commit_hash')
                if not expected_hash:
                    return False
                result = subprocess.run(["git", "write-tree"], cwd=repo_dir, capture_output=True, text=True)
                if result.returncode != 0:
                    return False
                current_tree = result.stdout.strip()

                subprocess.run(["git", "fetch", "origin", expected_hash], cwd=repo_dir, capture_output=True)
                result = subprocess.run(
                    ["git", "rev-parse", f"{expected_hash}^{{tree}}"],
                    cwd=repo_dir, capture_output=True, text=True
                )
                if result.returncode != 0:
                    return False
                expected_tree = result.stdout.strip()
                return current_tree == expected_tree

            elif sample_type == "file_commit_chain":
                file_path = scenario.get('file')
                newest = scenario.get('newest_commit')
                if not file_path or not newest:
                    return False

                result = subprocess.run(
                    ["git", "ls-tree", "-r", newest, "--", file_path],
                    cwd=repo_dir, capture_output=True, text=True
                )
                if result.returncode != 0 or not result.stdout.strip():
                    return False
                parts = result.stdout.strip().split()
                if len(parts) < 3:
                    return False
                target_hash = parts[2]

                full_path = repo_dir / file_path
                if not full_path.exists():
                    return False
                result = subprocess.run(
                    ["git", "hash-object", str(full_path)],
                    cwd=repo_dir, capture_output=True, text=True
                )
                if result.returncode != 0:
                    return False
                return result.stdout.strip() == target_hash

        except Exception as e:
            logger.error(f"Eval error: {e}")
            return False

        return False

    def run(self, num_tasks=None, task_ids=None):
        results = []
        tasks = list(self.dataset)
        if task_ids:
            tasks = [t for t in tasks if t['id'] in task_ids]
        elif num_tasks:
            tasks = tasks[:num_tasks]

        logger.info(f"Running {len(tasks)} tasks...")

        for i, task in enumerate(tasks):
            task_id = task['id']
            logger.info(f"[{i+1}/{len(tasks)}] {task_id}")

            start = time.time()
            error = None
            success = False

            try:
                repo_dir = self.setup_task(task)
                prompt = self.build_prompt(task)
                if self.run_codex(repo_dir, prompt):
                    success = self.evaluate(task, repo_dir)
                else:
                    error = "Codex failed"
            except Exception as e:
                error = str(e)
                logger.error(f"Task failed: {e}")

            elapsed = time.time() - start
            results.append(TaskResult(
                task_id=task_id,
                sample_type=task['sample_type'],
                success=success,
                execution_time_sec=elapsed,
                error=error
            ))
            logger.info(f"  {'PASS' if success else 'FAIL'} ({elapsed:.1f}s)")

        return results

    def save(self, results, path):
        data = {
            "benchmark": "git_good_bench",
            "agent": "codex",
            "total": len(results),
            "passed": sum(1 for r in results if r.success),
            "rate": sum(1 for r in results if r.success) / len(results) if results else 0,
            "results": [asdict(r) for r in results]
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved to {path}")
        logger.info(f"Result: {data['passed']}/{data['total']} ({data['rate']*100:.1f}%)")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-tasks", type=int, default=None)
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--output", default="codex_results.json")
    parser.add_argument("--work-dir", default="./codex_workdir")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("CODEX_API_KEY"):
        logger.error("OPENAI_API_KEY or CODEX_API_KEY not set")
        sys.exit(1)

    runner = CodexBenchRunner(work_dir=args.work_dir)
    results = runner.run(num_tasks=args.num_tasks, task_ids=args.task_ids)
    runner.save(results, args.output)


if __name__ == "__main__":
    main()
