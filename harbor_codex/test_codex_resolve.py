import subprocess
import os

os.chdir("/Users/hughliu/Desktop/git-good-bench/harbor_codex/codex_workdir/mockito_mockito_merge_0002/repo")

prompt = """You need to resolve the merge conflict in this repository.

Steps:
1. First, view the conflicted file to see what needs to be fixed:
   cat src/main/java/org/mockito/Mockito.java | grep -A 20 "<<<<<<<"

2. After understanding the conflict, you need to:
   - Keep BOTH sides of the conflict (merge them together)
   - Remove all conflict markers (<<<<<<, ======, >>>>>>)
   - Use 'git add' to stage the file

3. For the deleted file (src/test/java/org/mockitousage/verification/DelayedExecution.java):
   - This file was deleted in the merge. Use 'git rm' to confirm the deletion

4. After handling all files, commit with:
   git commit --no-edit

Start by viewing the conflicted file content."""

result = subprocess.run(
    ["codex", "exec", "--full-auto", "--model", "gpt-5", prompt],
    capture_output=True, text=True, timeout=600
)

print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
