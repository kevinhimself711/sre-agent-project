"""Install pinned upstream environments and execute the relevant offline regressions."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    name = sys.argv[1]
    repo = ROOT / "repos" / name
    results = ROOT / "test-results"
    results.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "POETRY_VIRTUALENVS_IN_PROJECT": "true",
    }
    # uv run activates the project's environment; upstreams must not install into it.
    env.pop("VIRTUAL_ENV", None)
    if name == "holmesgpt":
        subprocess.run(["uv", "tool", "install", "poetry==2.4.3"], check=True)
        poetry = str(
            Path(subprocess.check_output(["uv", "tool", "dir", "--bin"], text=True).strip())
            / "poetry"
        )
        subprocess.run(
            [poetry, "env", "use", sys.executable],
            cwd=repo,
            env=env,
            check=True,
        )
        subprocess.run(
            [poetry, "install", "--with", "dev", "--no-interaction"],
            cwd=repo,
            env=env,
            check=True,
        )
        tests = [
            "tests/core/test_episode_trace.py",
            "tests/test_mcp_toolset.py",
            "tests/test_mcp_content_errors.py",
            "tests/test_tool_calling_llm.py",
        ]
        tests.extend(
            str(p.relative_to(repo)) for p in (repo / "tests/core").glob("test_diagnosis_review.py")
        )
        args = ["--no-cov", "-n", "0", "-o", "log_cli=false", "-k", "not everything_stdio"]
    elif name == "sregym":
        subprocess.run(["uv", "sync", "--frozen", "--python", sys.executable], cwd=repo, check=True)
        tests = [
            "tests/traces",
            "tests/service/test_k8s_proxy.py",
            "tests/service/test_credential_mounts.py",
            "tests/service/test_container_images.py",
        ]
        args = []
    else:
        raise ValueError(name)
    python = repo / ".venv/bin/python"
    subprocess.run(
        [
            str(python),
            "-m",
            "pytest",
            *tests,
            *args,
            "-q",
            f"--junitxml={results / (name + '.xml')}",
        ],
        cwd=repo,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
