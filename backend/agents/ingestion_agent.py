"""Ingestion Agent — clones a GitHub repo or validates a local path."""
import os
import stat
import shutil
import tempfile
import asyncio
from urllib.parse import urlparse


def _force_remove_readonly(func, path, exc_info):
    """rmtree onerror callback — chmod +w then retry. Needed on Windows
    where Git marks pack-*.idx files read-only."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _safe_rmtree(target: str):
    """Cross-platform recursive delete that handles Git's read-only files."""
    if not os.path.exists(target):
        return
    # First pass: walk the tree and flip every read-only bit
    for root, dirs, files in os.walk(target):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), stat.S_IWRITE)
            except Exception:
                pass
        for f in files:
            try:
                os.chmod(os.path.join(root, f), stat.S_IWRITE)
            except Exception:
                pass
    # Second pass: actual delete, with onerror fallback for anything we missed
    try:
        shutil.rmtree(target, onerror=_force_remove_readonly)
    except Exception:
        # Last-ditch: try again after a short wait — Windows sometimes
        # holds file handles open briefly after a process exits.
        import time
        time.sleep(0.5)
        shutil.rmtree(target, onerror=_force_remove_readonly)


class IngestionAgent:
    def __init__(self, workspace: str = None):
        self.workspace = workspace or os.path.join(tempfile.gettempdir(), "codegraph_repos")
        os.makedirs(self.workspace, exist_ok=True)

    async def run(self, source: str, source_type: str):
        if source_type == "github":
            return await self._clone_github(source)
        elif source_type == "local":
            return self._load_local(source)
        else:
            raise ValueError(f"Unknown source_type: {source_type}")

    async def _clone_github(self, url: str):
        parsed = urlparse(url)
        if parsed.netloc not in ("github.com", "www.github.com"):
            raise ValueError("Only github.com URLs supported")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError("URL must be of the form https://github.com/owner/repo")
        owner, repo = parts[0], parts[1].replace(".git", "")

        target = os.path.join(self.workspace, f"{owner}__{repo}")
        if os.path.exists(target):
            _safe_rmtree(target)

        clone_url = f"https://github.com/{owner}/{repo}.git"
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", clone_url, target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {stderr.decode()}")

        return target, {"source": url, "owner": owner, "repo": repo, "local_path": target}

    def _load_local(self, path: str):
        if not os.path.isdir(path):
            raise ValueError(f"local path not found: {path}")
        return path, {
            "source": path,
            "owner": "local",
            "repo": os.path.basename(path.rstrip("/").rstrip("\\")),
            "local_path": path,
        }
