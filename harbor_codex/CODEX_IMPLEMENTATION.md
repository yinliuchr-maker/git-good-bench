# Codex Agent Implementation

This document describes the Codex agent implementation for GitGoodBench.

## Overview

The `codex_agent.py` module provides a complete implementation of the Codex agent that integrates with the GitGoodBench benchmark. It uses OpenAI's code-davinci-002 model to solve Git-related tasks.

## Architecture

### CodexAgent Class

The main component is the `CodexAgent` class, which:

1. **Initialization**: Takes an OpenAI API key (or reads from `OPENAI_API_KEY` environment variable)
2. **Task Solving**: Provides methods to solve two types of tasks:
   - `solve_merge_task()`: Solves merge conflict resolution tasks
   - `solve_file_commit_chain_task()`: Solves file commit chain manipulation tasks
3. **Prompt Building**: Constructs task-specific prompts for Codex
4. **API Integration**: Calls OpenAI's Codex API with appropriate parameters
5. **Command Execution**: Executes returned git commands in the repository

### Key Features

- **Task-Specific Prompts**: Different prompt templates for merge vs. file chain tasks
- **Error Handling**: Graceful handling of API errors and command execution failures
- **Command Validation**: Ensures returned commands are valid git commands
- **Timeout Protection**: Commands are executed with timeouts to prevent hanging
- **Logging**: Detailed error messages for debugging

## Usage

### As a Module

```python
from codex_agent import CodexAgent

# Initialize agent with API key
agent = CodexAgent(api_key="sk-...")

# Or use environment variable
import os
os.environ['OPENAI_API_KEY'] = "sk-..."
agent = CodexAgent()

# Solve tasks
merge_result = agent.solve_merge_task(task_description, repo_path)
chain_result = agent.solve_file_commit_chain_task(task_description, repo_path)
```

### Command Line

```bash
# Solve a merge task
python codex_agent.py --task-type merge --task-file task.json --repo-path ./repo

# Solve a file chain task
python codex_agent.py --task-type file_chain --task-file task.json --repo-path ./repo
```

## Integration with Harbor

The CodexAgent is designed to work with the Harbor framework:

```bash
# Set API key
export OPENAI_API_KEY=<your-api-key>

# Run evaluation on all 120 tasks
cd /path/to/harbor
uv run harbor jobs start -p datasets/git_good_bench --agent codex --n-concurrent 4
```

## API Integration Details

### Request Format

The agent sends requests to OpenAI's completion API:

```json
{
  "model": "code-davinci-002",
  "prompt": "Task description...",
  "temperature": 0.5,
  "max_tokens": 500,
  "stop": ["\n\n"]
}
```

### Response Parsing

The response is parsed to extract git commands:

1. Get the `text` field from the first choice
2. Split by newlines
3. Filter out empty lines
4. Execute each command sequentially

## Task Types

### Merge Conflict Resolution

The prompt instructs Codex to:
1. Analyze the merge conflict
2. Generate appropriate git commands to resolve it
3. Ensure the final state matches the target commit

Example prompt structure:
```
You are an expert Git user solving merge conflict resolution tasks.

Task Description: <task details>
Repository: <repo path>

Instructions:
1. Analyze the merge conflict
2. Generate appropriate git commands to resolve it
3. Ensure the final state matches the target commit

Provide ONLY the git commands...
```

### File Commit Chain

The prompt instructs Codex to:
1. Understand the target file state
2. Generate git commands to achieve it
3. Manipulate commits and file history as needed
4. Ensure the final file matches the target state

## Error Handling

The agent handles various error scenarios:

- **Missing API Key**: Raises ValueError if OPENAI_API_KEY is not set
- **API Errors**: Returns empty list if API call fails
- **Command Execution Errors**: Stops execution and returns False on first error
- **Network Issues**: Catches timeouts and connection errors

## Performance Characteristics

- **Temperature**: 0.5 (balanced between deterministic and creative)
- **Max Tokens**: 500 (sufficient for git command sequences)
- **Timeout**: 30 seconds for API calls, 10 seconds per command
- **Concurrency**: Supports concurrent execution via Harbor framework

## Future Enhancements

1. **Caching**: Cache Codex responses for repeated tasks
2. **Validation**: Validate commands before execution
3. **Fallback Strategies**: Implement fallback prompts if initial strategy fails
4. **Metrics Collection**: Track success rates by task type
5. **Fine-tuning**: Experiment with different prompt engineering techniques

## References

- [OpenAI Codex Documentation](https://platform.openai.com/docs/guides/code)
- [GitGoodBench Dataset](https://huggingface.co/datasets/JetBrains/git_good_bench)
- [Harbor Framework](https://harborframework.com/)
