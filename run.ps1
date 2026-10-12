param(
    [Parameter(Position=0)]
    [ValidateSet("dev", "test", "lint", "format", "setup")]
    [string]$Task = "dev"
)

$PYTHON = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$PIP = if (Test-Path ".\.venv\Scripts\pip.exe") { ".\.venv\Scripts\pip.exe" } else { "pip" }

switch ($Task) {
    "setup" {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
        python -m venv .venv
        & $PIP install -e ".[dev]"
    }
    "dev" {
        Write-Host "Starting NUST LMS Helper API server..." -ForegroundColor Green
        & $PYTHON -m uvicorn app.main:app --reload --port 8000
    }
    "test" {
        Write-Host "Running test suite..." -ForegroundColor Yellow
        & $PYTHON -m pytest tests/ -v
    }
    "lint" {
        Write-Host "Running ruff check..." -ForegroundColor Magenta
        & $PYTHON -m ruff check .
    }
    "format" {
        Write-Host "Formatting code with ruff..." -ForegroundColor Blue
        & $PYTHON -m ruff format .
    }
}
