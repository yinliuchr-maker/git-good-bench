# Harbor Codex Agent for GitGoodBench

This module implements Codex CLI support for running GitGoodBench parity experiments with Harbor.

## Overview

This implementation enables running GitGoodBench tasks using OpenAI's Codex CLI agent, allowing for fair "agent vs agent" parity comparisons between the original benchmark and Harbor adapter.

## Files

- `run_codex_benchmark.py` - Main benchmark runner using Codex CLI
- `codex_agent.py` - Codex agent implementation
- `requirements_codex.txt` - Python dependencies
- `CODEX_IMPLEMENTATION.md` - Detailed implementation documentation
- `CODEX_AGENT_SUPPORT.md` - Agent support documentation

## Installation

```bash
# Install Codex CLI
npm install -g @openai/codex

# Install Python dependencies
pip install -r requirements_codex.txt
```

## Usage

```bash
# Set API key
export OPENAI_API_KEY="sk-xxx"

# Run benchmark (test with 5 tasks first)
python run_codex_benchmark.py --num-tasks 5 --output test_results.json

# Run full benchmark (120 tasks)
python run_codex_benchmark.py --num-tasks 120 --output codex_results.json
```

## Parity Experiment

This module is used for Harbor adapter parity experiments:
- **Original benchmark side**: Run `run_codex_benchmark.py` here
- **Harbor side**: Run `harbor jobs start -d git_good_bench -a codex`

Both sides use the same Codex CLI agent for fair comparison.

## Related

- Harbor PR: https://github.com/laude-institute/harbor/pull/423
- Original Benchmark: https://github.com/JetBrains-Research/git-good-bench
