import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add the root directory to path so we can import setup_brain
sys.path.append(str(Path(__file__).parent.parent))


def test_setup_brain_fails_on_missing_env(tmp_path, monkeypatch):
    """
    Test that the validation bar catches missing .env files
    """
    # Change working directory to a temp path without a .env
    monkeypatch.chdir(tmp_path)

    # Run the setup_brain script in a subprocess
    root_dir = Path(__file__).parent.parent
    script_path = root_dir / "setup_brain.py"

    result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)

    # It should fail (exit code 1) and warn about .env
    assert result.returncode == 1
    assert ".env file missing" in result.stdout


def test_docker_compose_syntax_is_valid():
    """
    Test that the docker-compose file is syntactically valid.
    This is part of the 'validation bar' to ensure the onboarding sprint deliverables work.
    """
    root_dir = Path(__file__).parent.parent
    compose_path = root_dir / "docker-compose.yml"

    # Skip if docker isn't installed in the test environment
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "config"], capture_output=True, text=True
        )
        # 0 means the file is valid according to docker compose
        if result.returncode != 0:
            pytest.fail(f"Invalid docker-compose.yml: {result.stderr}")
    except FileNotFoundError:
        pytest.skip("Docker is not installed on this system, skipping syntax validation.")


def test_docker_compose_gpu_syntax_is_valid():
    """
    Test that the base and gpu override compose files are syntactically valid together.
    """
    root_dir = Path(__file__).parent.parent
    compose_path = root_dir / "docker-compose.yml"
    gpu_compose_path = root_dir / "docker-compose.gpu.yml"

    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "-f", str(gpu_compose_path), "config"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(f"Invalid docker-compose override: {result.stderr}")
    except FileNotFoundError:
        pytest.skip("Docker is not installed on this system.")


def test_env_parsing_with_quotes(tmp_path, monkeypatch):
    """
    Test that setup_brain.py can correctly parse a .env file that has quoted strings
    and comments, ensuring it doesn't break path checking.
    """
    monkeypatch.chdir(tmp_path)
    env_content = 'BRAIN_VAULT_PATH="C:\\Test Vault" # inline comment\nOLLAMA_HOST=http://localhost'

    with open(".env", "w") as f:
        f.write(env_content)

    root_dir = Path(__file__).parent.parent
    script_path = root_dir / "setup_brain.py"

    env = os.environ.copy()
    env["IS_TEST"] = "true"
    # Clear any existing vault path that might interfere with the test
    if "BRAIN_VAULT_PATH" in env:
        del env["BRAIN_VAULT_PATH"]

    result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, env=env)

    # We expect a warning that the vault path doesn't exist, NOT a parse error.
    # We check for the existence of the warning message without being overly strict
    # about exact drive letter/backslash escaping which can vary by parser.
    assert "Vault path does NOT exist" in result.stdout
    assert "Test Vault" in result.stdout
    assert "Ollama" in result.stdout  # Should proceed to Ollama check
