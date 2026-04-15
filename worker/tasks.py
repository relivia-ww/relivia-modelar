"""
Celery tasks para clonagem de páginas via agente_clone.py.
Roda em processo separado — sem acesso ao contexto Flask.
Usa SQLAlchemy standalone para atualizar o banco.
"""
import os
import sys
import json
import time
import subprocess
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from .celery_app import celery

# SQLAlchemy standalone (fora do contexto Flask)
from sqlalchemy import create_engine, text

_engine = create_engine(
    os.environ.get("DATABASE_URL", "sqlite:///instance/relivia_modelar.db"),
    connect_args={"check_same_thread": False},
)


def _update_job(job_id: str, **kwargs):
    """Atualiza campos do CloneJob diretamente via SQL."""
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    kwargs["job_id"] = job_id
    with _engine.connect() as conn:
        conn.execute(text(f"UPDATE clone_jobs SET {sets} WHERE id = :job_id"), kwargs)
        conn.commit()


def _slug(text_: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", text_.lower()).strip("-")[:40]


@celery.task(bind=True, name="worker.tasks.run_clone")
def run_clone(self, job_id: str, url: str, page_type: str, nome_pasta: str):
    """
    Tarefa principal: clona uma URL usando agente_clone.py.
    Salva output em runs/<job_id>/ e atualiza DB.
    """
    agente_script = Path(os.environ.get(
        "AGENTE_CLONE_SCRIPT",
        r"C:/Users/user/Desktop/Obsidian Supremo/Otimizacao de escala/agente-clone/agente_clone.py"
    ))
    runs_base = Path(os.environ.get("AGENTE_CLONE_RUNS_BASE", "C:/projetos/relivia-modelar/runs"))
    job_dir = runs_base / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        _update_job(job_id, status="running", progress_msg="Preparando clonagem...")

        # Monta funil-data.json sintético
        brand = nome_pasta or _slug(url.split("//")[-1].split("/")[0])
        funil_data = {
            "brand": brand,
            "destination_urls_typed": [{"url": url, "tipo": page_type, "produto_url": url}],
            "destination_urls_clean": [url],
            "destination_urls": [{"url": url, "clean_url": url, "peso": 1, "anuncios": 1}],
            "top_ads_copy": [],
        }
        funil_json = job_dir / "funil-data.json"
        funil_json.write_text(json.dumps(funil_data, ensure_ascii=False), encoding="utf-8")

        _update_job(job_id, progress_msg="DrissionPage abrindo a página...")

        # Executa o agente clone
        result = subprocess.run(
            [sys.executable, str(agente_script), "--json", str(funil_json)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(agente_script.parent),
            timeout=540,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr[-2000:] or "Agente retornou erro sem mensagem")

        _update_job(job_id, progress_msg="Localizando output gerado...")

        # Localiza index.html gerado pelo agente (cria em runs/ relativo ao script)
        agente_runs = agente_script.parent / "runs"
        candidates = sorted(
            agente_runs.glob(f"*{_slug(brand[:10])}*/index.html"),
            key=lambda p: p.stat().st_mtime,
        )
        if not candidates:
            # fallback: qualquer run criado nos últimos 10min
            candidates = sorted(agente_runs.glob("*/index.html"), key=lambda p: p.stat().st_mtime)
            candidates = [p for p in candidates if time.time() - p.stat().st_mtime < 600]

        if not candidates:
            raise RuntimeError("index.html não encontrado no output do agente")

        agente_run_dir = candidates[-1].parent

        # Copia output para job_dir
        import shutil
        dest_html = job_dir / "index.html"
        shutil.copy2(agente_run_dir / "index.html", dest_html)

        images_src = agente_run_dir / "images"
        images_dest = job_dir / "images"
        if images_src.exists():
            if images_dest.exists():
                shutil.rmtree(images_dest)
            shutil.copytree(images_src, images_dest)

        # Para advertorial: injeta CSS Relívia inline
        if page_type == "advertorial":
            _inject_adv_css(dest_html)

        # Conta imagens
        n_images = len(list(images_dest.glob("*"))) if images_dest.exists() else 0

        _update_job(
            job_id,
            status="done",
            progress_msg=f"Concluído — {n_images} imagens baixadas",
            out_dir=str(job_dir),
            html_path=str(dest_html),
            images_count=n_images,
        )

    except subprocess.TimeoutExpired:
        _update_job(job_id, status="error", error_msg="Timeout: agente demorou mais de 9 minutos")
    except Exception as e:
        _update_job(job_id, status="error", error_msg=str(e)[:1000])


def _inject_adv_css(html_path: Path):
    """Injeta CSS do template advertorial Relívia no <head> se não tiver <style> próprio."""
    css_path = Path(__file__).parent.parent / "app" / "static" / "css" / "relivia-advertorial.css"
    if not css_path.exists():
        return
    html = html_path.read_text(encoding="utf-8", errors="replace")
    if "<style>" not in html[:1000]:
        css = css_path.read_text(encoding="utf-8")
        html = html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
        html_path.write_text(html, encoding="utf-8")
