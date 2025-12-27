# Codex Agent Support for GitGoodBench

This fork includes support for running evaluations with the Codex agent on the GitGoodBench dataset.

## Overview

This document describes how to use the Codex agent (OpenAI code-davinci-002) to evaluate performance on GitGoodBench tasks within the Harbor framework.

## Prerequisites

1. **OpenAI API Key**: You need a valid OpenAI API key with access to Codex (code-davinci-002)
2. **Harbor Framework**: The benchmark is integrated into Harbor, so Harbor must be installed
3. **Git Environment**: Python 3.8+ with git installed

## Running Codex on GitGoodBench

### Setup

1. Set your OpenAI API key as an environment variable:
```bash
export OPENAI_API_KEY=<your-api-key>
```

2. Clone or navigate to your Harbor installation with this dataset

### Execution

Run the full benchmark on all 120 tasks using Codex agent:

```bash
cd /path/to/harbor

# Run evaluation with 4 concurrent workers
uv run harbor jobs start -p datasets/git_good_bench --agent codex --n-concurrent 4
```

For testing with a smaller subset:
```bash
uv run harbor jobs start -p datasets/git_good_bench --agent codex --n-concurrent 4 --max-tasks 10
```

## Task Types

GitGoodBench includes two types of tasks:

### 1. Merge Conflict Resolution (60 tasks)
- **Objective**: Resolve merge conflicts in git repositories
- **Evaluation**: Tree hash comparison (git write-tree)
- **Verification**: Agent's resolved state must match the expected merge commit

### 2. File Commit Chain Tasks (60 tasks)
- **Objective**: Manipulate file history through git commits
- **Evaluation**: Blob hash comparison (git ls-tree)
- **Verification**: Agent's file state must match the target commit

## Expected Behavior

The Codex agent will:
1. Receive task instructions describing a git scenario
2. Have access to a Git CLI interface
3. Attempt to resolve the task through git commands
4. Be evaluated based on the final repository state

## Integration with Harbor

This fork is designed to work seamlessly with Harbor's evaluation framework:
- Tasks are dynamically generated from the dataset
- Evaluation is automatic via Harbor's validation pipeline
- Results are collected and can be compared against other agents (Oracle, etc.)

## Results

Results from Codex evaluations on this benchmark are tracked in the main Harbor adapter:
- **parity_experiment.json**: Contains Codex performance metrics
- **CODEX_PARITY.md**: Detailed documentation of the parity experiment

## References

- **Original Benchmark**: https://github.com/JetBrains-Research/git-good-bench
- **Harbor Adapter**: https://github.com/laude-institute/harbor/pull/321
- **Parity Experiment**: https://github.com/laude-institute/harbor-datasets/pull/42

## Support

For issues or questions about running Codex on GitGoodBench:
1. Check the Harbor documentation: https://harborframework.com/docs
2. Review the adapter README in the main Harbor repository
3. Open an issue on the harbor repository
