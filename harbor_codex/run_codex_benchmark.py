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
    def __init__(self, work_dir="./codex_workdir", model="gpt-5-nano"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        logger.info(f"Using model: {model}")
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

        conflict_info = None  # Will store extracted conflict info for merge tasks
        
        if sample_type == "merge":
            parents = scenario.get('parents', [])
            if len(parents) >= 2:
                subprocess.run(["git", "fetch", "origin", parents[0]], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "checkout", parents[0]], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "fetch", "origin", parents[1]], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "merge", parents[1], "--no-commit"], cwd=repo_dir, capture_output=True)
                
                # Extract conflict information to provide to agent (like original baseline does)
                conflict_info = self._extract_conflict_info(repo_dir)
                
        elif sample_type == "file_commit_chain":
            oldest = scenario.get('oldest_commit')
            if oldest:
                subprocess.run(["git", "fetch", "origin", oldest], cwd=repo_dir, capture_output=True)
                subprocess.run(["git", "checkout", oldest], cwd=repo_dir, capture_output=True)

        return repo_dir, conflict_info

    def _extract_conflict_info(self, repo_dir):
        """Extract merge conflict information to provide to the agent (similar to original baseline)."""
        conflict_info = {"files": [], "conflicts": []}
        
        # Get list of unmerged files
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=repo_dir, capture_output=True, text=True
        )
        unmerged_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        conflict_info["files"] = unmerged_files
        
        # Extract conflict content from each file
        for i, filepath in enumerate(unmerged_files[:10]):  # Limit to first 10 files
            full_path = repo_dir / filepath
            if full_path.exists():
                try:
                    content = full_path.read_text(errors='replace')
                    # Find conflict markers
                    if '<<<<<<<' in content:
                        # Extract just the conflict sections (not entire file)
                        lines = content.split('\n')
                        in_conflict = False
                        conflict_text = []
                        for line in lines:
                            if line.startswith('<<<<<<<'):
                                in_conflict = True
                                conflict_text.append(line)
                            elif in_conflict:
                                conflict_text.append(line)
                                if line.startswith('>>>>>>>'):
                                    in_conflict = False
                        
                        if conflict_text:
                            # Limit conflict text size
                            conflict_str = '\n'.join(conflict_text[:100])  # First 100 lines of conflicts
                            conflict_info["conflicts"].append({
                                "index": i,
                                "file": filepath,
                                "content": conflict_str[:3000]  # Limit to 3000 chars
                            })
                except Exception as e:
                    logger.warning(f"Could not read {filepath}: {e}")
        
        return conflict_info

    def build_prompt(self, task, conflict_info=None):
        scenario = ast.literal_eval(task['scenario']) if isinstance(task['scenario'], str) else task['scenario']
        sample_type = task['sample_type']

        if sample_type == "merge":
            conflict_files = scenario.get('files_in_merge_conflict', [])
            if not conflict_files:
                conflict_files = []
            
            # Build prompt similar to original baseline - provide conflict content directly
            prompt = """You are a staff software engineer resolving git merge conflicts.

TASK: Resolve all merge conflicts and complete the merge.

"""
            # Add conflict file list
            if conflict_info and conflict_info.get("files"):
                prompt += f"Files with merge conflicts:\n"
                for f in conflict_info["files"]:
                    prompt += f"  - {f}\n"
                prompt += "\n"
            elif conflict_files:
                prompt += f"Files with merge conflicts:\n"
                for f in conflict_files[:10]:
                    prompt += f"  - {f}\n"
                prompt += "\n"
            
            # Add actual conflict content (like original baseline's {all_merge_conflicts})
            if conflict_info and conflict_info.get("conflicts"):
                prompt += "MERGE CONFLICTS TO RESOLVE:\n"
                prompt += "=" * 50 + "\n"
                for conf in conflict_info["conflicts"]:
                    prompt += f"\n<CONFLICT-{conf['index']}>\n"
                    prompt += f"File: {conf['file']}\n"
                    prompt += f"{conf['content']}\n"
                    prompt += f"</CONFLICT-{conf['index']}>\n"
                prompt += "=" * 50 + "\n\n"
            
            prompt += """INSTRUCTIONS:
1. For each conflict shown above:
   - Analyze both sides (between <<<<<<< and =======, and between ======= and >>>>>>>)
   - Decide which content to keep (or merge both)
   - Edit the file to remove ALL conflict markers and keep the correct content

2. Use these commands:
   - View file: cat <filepath>
   - Edit file: Use sed, echo with redirect, or create with cat << 'EOF'
   - Stage resolved file: git add <filepath>

3. After resolving all conflicts:
   - Verify: git diff --name-only --diff-filter=U (should be empty)
   - Complete: git commit --no-edit

IMPORTANT:
- Remove ALL conflict markers (<<<<<<<, =======, >>>>>>>)
- Do NOT use git mergetool
- Make sure the final code is syntactically correct
"""
            return prompt

        elif sample_type == "file_commit_chain":
            return f"""Update the target file to match the expected state at a specific git commit.

Instructions:
1. Get the target file content from the target commit: git show <commit>:<filepath>
2. Compare with current file content: cat <filepath>
3. If they differ, edit the file to match the target exactly
4. Verify: git hash-object <filepath>

Target file: {scenario.get('file', 'N/A')}
Target commit: {scenario.get('newest_commit', 'N/A')}"""

        return "Unknown task"

    def run_codex(self, repo_dir, prompt, timeout=600):
        try:
            env = {**os.environ}
            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CODEX_API_KEY")
            if api_key:
                env["CODEX_API_KEY"] = api_key

            result = subprocess.run(
                ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "--model", self.model, prompt],
                cwd=repo_dir, capture_output=True, text=True, timeout=timeout, env=env
            )
            
            # Codex may return non-zero even when it completed work
            # We'll check the actual repo state in evaluate() instead
            if result.returncode != 0:
                logger.debug(f"Codex returned non-zero: {result.returncode}")
            
            # Return True to continue to evaluation - let evaluate() determine success
            return True
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout after {timeout}s")
            return True  # Still evaluate - partial work may have been done
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
                    logger.warning(f"No merge_commit_hash in scenario")
                    return False
                
                # Check if there are still unmerged paths
                result = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=U"],
                    cwd=repo_dir, capture_output=True, text=True
                )
                unmerged = result.stdout.strip()
                if unmerged:
                    logger.warning(f"Unmerged files remain: {unmerged}")
                    return False
                
                result = subprocess.run(["git", "write-tree"], cwd=repo_dir, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"git write-tree failed: {result.stderr}")
                    return False
                current_tree = result.stdout.strip()

                subprocess.run(["git", "fetch", "origin", expected_hash], cwd=repo_dir, capture_output=True)
                result = subprocess.run(
                    ["git", "rev-parse", f"{expected_hash}^{{tree}}"],
                    cwd=repo_dir, capture_output=True, text=True
                )
                if result.returncode != 0:
                    logger.warning(f"Could not get expected tree: {result.stderr}")
                    return False
                expected_tree = result.stdout.strip()
                
                match = current_tree == expected_tree
                if not match:
                    logger.warning(f"Tree mismatch: got {current_tree}, expected {expected_tree}")
                return match

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
                repo_dir, conflict_info = self.setup_task(task)
                prompt = self.build_prompt(task, conflict_info)
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
            "agent": f"codex@{self.model}",
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
    parser.add_argument("--model", default="gpt-5-nano", help="Model to use (e.g., gpt-5-nano, gpt-5-mini)")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("CODEX_API_KEY"):
        logger.error("OPENAI_API_KEY or CODEX_API_KEY not set")
        sys.exit(1)

    runner = CodexBenchRunner(work_dir=args.work_dir, model=args.model)
    results = runner.run(num_tasks=args.num_tasks, task_ids=args.task_ids)
    runner.save(results, args.output)


if __name__ == "__main__":
    main()
