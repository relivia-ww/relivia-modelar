"""
Vercel REST API — trigger de deploy e polling de status.
O deploy é acionado automaticamente pelo webhook do GitHub.
Este serviço monitora o deploy mais recente até ficar READY.
"""
import time
import requests


class VercelService:
    def __init__(self, token: str, project_id: str):
        self.token = token
        self.project_id = project_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get_latest_deployment(self) -> dict:
        """Retorna o deployment mais recente do projeto."""
        r = requests.get(
            f"https://api.vercel.com/v6/deployments",
            headers=self.headers,
            params={"projectId": self.project_id, "limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        deployments = r.json().get("deployments", [])
        return deployments[0] if deployments else {}

    def poll_until_ready(self, timeout: int = 180) -> dict:
        """
        Faz polling até o deploy mais recente ficar READY ou ERROR.
        Retorna dict com { status, url, error }.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            deploy = self.get_latest_deployment()
            state = deploy.get("state", "")
            ready_state = deploy.get("readyState", "")
            url = deploy.get("url", "")

            if ready_state in ("READY", "ERROR", "CANCELED"):
                return {
                    "status": ready_state,
                    "url": f"https://{url}" if url and not url.startswith("http") else url,
                    "deploy_id": deploy.get("uid", ""),
                    "error": deploy.get("errorMessage", "") if ready_state == "ERROR" else "",
                }
            time.sleep(5)

        return {"status": "TIMEOUT", "url": "", "deploy_id": "", "error": "Timeout aguardando deploy"}

    def trigger_redeploy(self, deploy_id: str) -> dict:
        """Re-faz um deploy existente (útil se o webhook não disparou)."""
        r = requests.post(
            f"https://api.vercel.com/v13/deployments?forceNew=1",
            headers=self.headers,
            json={"deploymentId": deploy_id},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
