# Vera AI Challenge Submission

## Setup Environment
Create and use the project-local virtual environment:
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```
*(On Linux/Mac use `python -m venv .venv` and `source .venv/bin/activate`)*

## Configuration
Create a `.env` file in the root directory:
```env
# Required for Gemini evaluation mode (optional for baseline tests)
GEMINI_API_KEY=your_key_here
```

## Running the Application
Start the FastAPI server:
```powershell
.\.venv\Scripts\python.exe -m uvicorn vera.adapters.fastapi_app:app --port 8080
```

## Running Tests
Run the deterministic unit test suite:
```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Offline Evaluation
Run the deterministic regression baseline (evaluates the engine without requiring Gemini):
```powershell
.\.venv\Scripts\python.exe tools/evaluate_baseline.py
```

Run the conversation state machine replay tool:
```powershell
.\.venv\Scripts\python.exe tools/replay_conversations.py
```
