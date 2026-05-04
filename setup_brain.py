import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_step(msg):
    print(f"\n{Colors.BOLD}>>> {msg}{Colors.RESET}")

def print_success(msg):
    print(f"  {Colors.GREEN}[OK] {msg}{Colors.RESET}")

def print_error(msg):
    print(f"  {Colors.RED}[FAIL] {msg}{Colors.RESET}")

def print_warn(msg):
    print(f"  {Colors.YELLOW}[WARN] {msg}{Colors.RESET}")

def check_python_version():
    print_step("Checking Python Version")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print_success(f"Python version is {version.major}.{version.minor} (Supported)")
        return True
    else:
        print_error(f"Python version is {version.major}.{version.minor}. Required: 3.10+")
        return False

def check_env_file():
    print_step("Checking Environment Configuration")
    if os.path.exists(".env"):
        print_success(".env file found")
        env_vars = {}
        try:
            from dotenv import dotenv_values
            env_vars = dotenv_values(".env")
            print_success("Parsed .env using python-dotenv")
        except ImportError:
            print_warn("python-dotenv not installed. Falling back to custom parser.")
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        try:
                            # Use shlex to cleanly handle quotes
                            s = shlex.shlex(line, posix=True, punctuation_chars='=')
                            s.commenters = '#'
                            parts = list(s)
                            if len(parts) >= 3 and parts[1] == '=':
                                # Join anything after '=' just in case
                                env_vars[parts[0]] = "".join(parts[2:]).strip()
                        except ValueError:
                            pass

        # Merge os.environ so Docker overrides take precedence
        env_vars.update(os.environ)

        if os.environ.get("IS_DOCKER") == "true":
            print_success("Running inside Docker. Skipping host path validation.")
            return True, env_vars

        vault_path = env_vars.get("BRAIN_VAULT_PATH", "")
        if vault_path:
            if os.path.exists(vault_path):
                print_success(f"Vault path exists: {vault_path}")
            else:
                print_warn(f"Vault path does NOT exist: {vault_path}. Please create it before indexing.")
        else:
            print_warn("BRAIN_VAULT_PATH not set in .env. Will use defaults.")

        return True, env_vars
    else:
        print_error(".env file missing. Please copy .env.example to .env")
        return False, {}

def check_ollama(env_vars):
    print_step("Checking Ollama Connection")

    if env_vars.get("IS_TEST") == "true":
        print_success("Test mode detected. Skipping Ollama connection.")
        return True

    host = env_vars.get("OLLAMA_HOST", "http://127.0.0.1:11434")

    # 1. Check if the server is responsive
    max_retries = 5
    connected = False
    data = {}
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(f"{host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                print_success(f"Connected to Ollama at {host}")
                connected = True
                break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt < max_retries - 1:
                print_warn(f"Could not connect to Ollama. Retrying in 2 seconds... ({attempt+1}/{max_retries})")
                time.sleep(2)
            else:
                print_error(f"Could not connect to Ollama at {host} after {max_retries} attempts. Is the service running?")
                return False

    if not connected:
        return False

    # 2. Check if required models are pulled
    required_models = [
        env_vars.get("BRAIN_LOCAL_MODEL", "qwen3.5:4b-brain"),
        env_vars.get("BRAIN_EMBED_MODEL", "nomic-embed-text")
    ]

    available_models = [m["name"] for m in data.get("models", [])]

    all_models_present = True
    for model in required_models:
        # Ollama often returns tags like 'nomic-embed-text:latest'
        if model in available_models or f"{model}:latest" in available_models:
            print_success(f"Model found: {model}")
        else:
            print_error(f"Model missing: {model}. Run `ollama pull {model}`")
            all_models_present = False

    return all_models_present

def main():
    print(f"{Colors.BOLD}ZeroCostBrain - Pre-Flight Environment Validation{Colors.RESET}")
    print("=" * 50)

    checks_passed = True

    if not check_python_version():
        checks_passed = False

    env_ok, env_vars = check_env_file()
    if not env_ok:
        checks_passed = False

    # Only check ollama if the provider is local
    provider = env_vars.get("BRAIN_LLM_PROVIDER", "LOCAL")
    if provider == "LOCAL":
        if not check_ollama(env_vars):
            checks_passed = False
    else:
        print_step("Checking Gemini API")
        if env_vars.get("GOOGLE_API_KEY"):
            print_success("GOOGLE_API_KEY is configured")
        else:
            print_error("GOOGLE_API_KEY is missing from .env")
            checks_passed = False

    print("\n" + "=" * 50)
    if checks_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}All checks passed! You are ready to start the Brain.{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}Some checks failed. Please resolve the issues above before continuing.{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
