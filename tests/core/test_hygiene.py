import os
import sys
import subprocess
import json
import ast
from pathlib import Path

def test_imports_and_package_initialization():
    try:
        import vera
        import vera.core
        import vera.core.models
        import vera.adapters
        import vera.config
        import vera.bootstrap
    except ImportError as e:
        pytest.fail(f"Package initialization failed: {e}")

def test_dataset_reproducibility(tmp_path):
    # Run the generator script
    script_path = Path("challenge/dataset/generate_dataset.py")
    seed_dir = Path("challenge/dataset")
    out_dir = tmp_path / "dataset_expanded"
    
    result = subprocess.run([
        sys.executable, str(script_path), 
        "--seed-dir", str(seed_dir), 
        "--out", str(out_dir)
    ], capture_output=True, text=True)
    
    assert result.returncode == 0, f"Generator failed: {result.stderr}"
    
    # Check counts based on expected expansion
    categories = list((out_dir / "categories").glob("*.json"))
    merchants = list((out_dir / "merchants").glob("*.json"))
    customers = list((out_dir / "customers").glob("*.json"))
    triggers = list((out_dir / "triggers").glob("*.json"))
    
    assert len(categories) == 5
    assert len(merchants) == 50
    assert len(customers) == 200
    assert len(triggers) == 100
    
    # Check canonical test pairs
    test_pairs_file = out_dir / "test_pairs.json"
    assert test_pairs_file.exists()
    
    with open(test_pairs_file, "r") as f:
        data = json.load(f)
        assert len(data.get("pairs", [])) == 30

def test_no_forbidden_imports():
    """Ensure production code does not import from research or challenge"""
    src_dir = Path("src/vera")
    
    for py_file in src_dir.rglob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            assert not alias.name.startswith("research"), f"Forbidden import in {py_file}: {alias.name}"
                            assert not alias.name.startswith("challenge"), f"Forbidden import in {py_file}: {alias.name}"
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            assert not node.module.startswith("research"), f"Forbidden import in {py_file}: {node.module}"
                            assert not node.module.startswith("challenge"), f"Forbidden import in {py_file}: {node.module}"
            except SyntaxError:
                pytest.fail(f"Syntax error in {py_file}")

def test_repository_hygiene():
    """Ensure no forbidden files are in the repository structure"""
    forbidden_extensions = [".env", ".secrets", ".credentials"]
    
    root_dir = Path(".")
    # Avoid checking within virtual environments if they exist, but we assume a clean run here.
    for ext in forbidden_extensions:
        # Just check the root
        assert not (root_dir / ext).exists(), f"Forbidden file found: {ext}"
