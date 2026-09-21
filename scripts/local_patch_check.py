from verify_patches import ROOT, verify

if __name__ == "__main__":
    verify(
        worktree=all((ROOT / "repos" / name / ".git").exists() for name in ("holmesgpt", "sregym"))
    )
