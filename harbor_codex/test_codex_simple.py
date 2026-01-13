import subprocess
import os

os.chdir("/Users/hughliu/Desktop/git-good-bench/harbor_codex/codex_workdir/mockito_mockito_merge_0002/repo")

# Simple test
prompt = """Run these git commands in order and report the output:
1. git status
2. git diff --name-only --diff-filter=U
"""

result = subprocess.run(
    ["codex", "exec", "--full-auto", "--model", "gpt-5-nano", prompt],
    capture_output=True, text=True, timeout=300
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print("\nReturn code:", result.returncode)
