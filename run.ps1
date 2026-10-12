param(
    [Parameter(Position=0)]
    [ValidateSet("dev", "test", "lint", "format", "setup")]
    [string]$Task = "dev"
)

switch ($Task) {
    "setup" {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
        python -m venv .venv
        & .\.venv\Scripts\pip.exe install -e ".[dev]"
    }
    "dev" {
        Write-Host "Starting NUST LMS Helper API server..." -ForegroundColor Green
        python -m uvicorn app.main:app --reload --port 8000
    }
    "test" {
        Write-Host "Running test suite..." -ForegroundColor Yellow
        python -m pytest tests/ -v
    }
    "lint" {
        Write-Host "Running ruff check and mypy..." -ForegroundColor Magenta
        python -m ruff check .
        python -m mypy app/
    }
    "format" {
        Write-Host "Formatting code with ruff..." -ForegroundColor Blue
        python -m ruff format .
    }
}
