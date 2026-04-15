"""
GitHub REST API v3 — commit de arquivos (HTML + imagens) em um repositório.
"""
import base64
import requests
from pathlib import Path


class GitHubService:
    def __init__(self, token: str, repo: str, branch: str = "main"):
        self.token = token
        self.repo = repo      # "owner/repo-name"
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{repo}/contents"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ReliviaModelar/1.0",
        }

    def _get_sha(self, path: str) -> str:
        """Retorna SHA atual do arquivo (necessário para update). '' se não existir."""
        r = requests.get(
            f"{self.base_url}/{path}",
            headers=self.headers,
            params={"ref": self.branch},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("sha", "")
        return ""

    def commit_file(self, path: str, content_bytes: bytes, message: str) -> dict:
        """Commita um arquivo. Cria ou atualiza. Retorna dict com sha e commit_url."""
        sha = self._get_sha(path)
        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(
            f"{self.base_url}/{path}",
            headers=self.headers,
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "path": path,
            "action": "updated" if sha else "created",
            "sha": data.get("content", {}).get("sha", ""),
            "commit_sha": data.get("commit", {}).get("sha", ""),
            "commit_url": data.get("commit", {}).get("html_url", ""),
        }

    def commit_job_files(self, nome_pasta: str, out_dir: Path) -> dict:
        """
        Commita index.html + todas as imagens de um job.
        Retorna { committed: int, skipped: int, commit_url: str, errors: list }
        """
        committed = []
        skipped = []
        last_commit_url = ""

        # 1 — index.html
        html_path = out_dir / "index.html"
        if not html_path.exists():
            raise FileNotFoundError("index.html não encontrado no job")

        result = self.commit_file(
            path=f"{nome_pasta}/index.html",
            content_bytes=html_path.read_bytes(),
            message=f"feat: modelar {nome_pasta} via Relívia Modelar",
        )
        committed.append(result)
        last_commit_url = result["commit_url"]

        # 2 — imagens
        images_dir = out_dir / "images"
        if images_dir.exists():
            for img in sorted(images_dir.iterdir()):
                if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
                    continue
                try:
                    r = self.commit_file(
                        path=f"{nome_pasta}/images/{img.name}",
                        content_bytes=img.read_bytes(),
                        message=f"feat: imagem {img.name} ({nome_pasta})",
                    )
                    committed.append(r)
                    last_commit_url = r["commit_url"]
                except Exception as e:
                    skipped.append({"name": img.name, "error": str(e)[:200]})

        return {
            "committed": len(committed),
            "skipped": len(skipped),
            "commit_url": last_commit_url,
            "files": committed,
            "errors": skipped,
        }
