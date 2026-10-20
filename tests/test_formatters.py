"""Unit tests for multi-format deliverable generators (ipynb, docx, xlsx)."""

import json
from pathlib import Path

from workers.formatters import (
    build_notebook_structure,
    convert_solution_to_notebook,
    create_jupyter_notebook,
)


def test_build_notebook_structure():
    """Verify Jupyter notebook schema adheres to nbformat v4."""
    cells = [
        {"cell_type": "markdown", "source": "# Lab 1 Title\nIntroduction"},
        {"cell_type": "code", "source": "def solution():\n    return 42"},
    ]
    nb = build_notebook_structure(cells)

    assert nb["nbformat"] == 4
    assert nb["nbformat_minor"] == 5
    assert len(nb["cells"]) == 2
    assert nb["cells"][0]["cell_type"] == "markdown"
    assert nb["cells"][1]["cell_type"] == "code"
    assert nb["metadata"]["language_info"]["name"] == "python"


def test_create_jupyter_notebook(tmp_path: Path):
    """Verify creation and JSON persistence of .ipynb files."""
    out_file = tmp_path / "lab_submission.ipynb"
    cells = [
        {"cell_type": "markdown", "source": "# Lab Exercise"},
        {"cell_type": "code", "source": "print('NUST')"},
    ]
    result_path = create_jupyter_notebook(cells, out_file)

    assert result_path.exists()
    content = json.loads(result_path.read_text(encoding="utf-8"))
    assert content["nbformat"] == 4
    assert len(content["cells"]) == 2


def test_convert_solution_to_notebook(tmp_path: Path):
    """Verify high-level conversion of solution code into submission notebook."""
    out_file = tmp_path / "complete_lab.ipynb"
    result = convert_solution_to_notebook(
        title="CS212 BST Lab",
        solution_code="class BSTNode: ...",
        walkthrough="This algorithm achieves O(log N) average time.",
        output_path=out_file,
        viva_questions=["What is tree rotation?"],
    )

    assert result.exists()
    data = json.loads(result.read_text(encoding="utf-8"))
    assert len(data["cells"]) == 4  # intro, code header, code, viva
    # Check that code cell has the solution code
    code_cells = [c for c in data["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) == 1
    assert "class BSTNode: ..." in "".join(code_cells[0]["source"])
