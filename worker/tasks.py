"""
Celery tasks — clonagem de landing pages via Crawl4AI.
Zero dependência de scripts locais. Roda 100% em cloud.
"""
import os
import re
import json
import base64
import asyncio
import shutil
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv

load_dotenv()

from .celery_app import celery
from sqlalchemy import create_engine, text

_engine = create_engine(
    os.environ.get("DATABASE_URL", "sqlite:///instance/relivia_modelar.db"),
    connect_args={"check_same_thread": False} if "sqlite" in os.environ.get("DATABASE_URL", "sqlite") else {},
)


def _update_job(job_id: str, **kwargs):
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    kwargs["job_id"] = job_id
    with _engine.connect() as conn:
        conn.execute(text(f"UPDATE clone_jobs SET {sets} WHERE id = :job_id"), kwargs)
        conn.commit()


def _slug(text_: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", text_.lower()).strip("-")[:40]


async def _scrape_page(url: str) -> dict:
    """
    Abre a URL com Crawl4AI (Playwright/Chromium headless).
    Retorna: html, screenshot (base64), lista de URLs de imagens.
    """
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import NoExtractionStrategy

    async with AsyncWebCrawler(
        headless=True,
        verbose=False,
    ) as crawler:
        result = await crawler.arun(
            url=url,
            screenshot=True,
            magic=True,
            simulate_user=True,
            wait_for="networkidle",
            page_timeout=60000,
            extraction_strategy=NoExtractionStrategy(),
        )

    if not result.success:
        raise RuntimeError(f"Crawl4AI falhou: {result.error_message}")

    # Coleta URLs de imagens do HTML + media dict
    image_urls = []
    seen = set()

    # Do media dict do Crawl4AI
    for img in result.media.get("images", []):
        src = img.get("src", "")
        if src and src not in seen:
            seen.add(src)
            image_urls.append(src)

    # Fallback: extrai <img src> do HTML com regex
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', result.html or ""):
        abs_src = urljoin(url, src)
        if abs_src not in seen:
            seen.add(abs_src)
            image_urls.append(abs_src)

    return {
        "html": result.html or "",
        "screenshot_b64": result.screenshot or "",
        "image_urls": image_urls,
    }


def _download_images(image_urls: list, dest_dir: Path, base_url: str) -> dict:
    """
    Baixa imagens e salva em dest_dir.
    Retorna mapa {url_original: nome_arquivo_local}.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    url_map = {}

    SKIP_DOMAINS = {
        "google-analytics.com", "googletagmanager.com", "doubleclick.net",
        "facebook.com", "facebook.net", "fbcdn.net", "hotjar.com",
        "clarity.ms", "tiktok.com", "segment.com", "mixpanel.com",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": base_url,
    }

    for i, img_url in enumerate(image_urls[:80]):  # máx 80 imagens
        try:
            parsed = urlparse(img_url)
            if any(d in parsed.netloc for d in SKIP_DOMAINS):
                continue
            if not parsed.scheme.startswith("http"):
                continue

            resp = requests.get(img_url, headers=headers, timeout=15, stream=True)
            if resp.status_code != 200:
                continue

            content_type = resp.headers.get("content-type", "image/jpeg")
            if not content_type.startswith("image/"):
                continue

            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png",
                "image/gif": ".gif", "image/webp": ".webp",
                "image/svg+xml": ".svg", "image/avif": ".avif",
            }
            ext = ext_map.get(content_type.split(";")[0].strip(), ".jpg")

            # Nome do arquivo baseado no path original
            orig_name = Path(parsed.path).stem[:40] or f"img_{i}"
            filename = f"{orig_name}{ext}"
            # Evita colisão
            counter = 1
            while (dest_dir / filename).exists():
                filename = f"{orig_name}_{counter}{ext}"
                counter += 1

            (dest_dir / filename).write_bytes(resp.content)
            url_map[img_url] = filename

        except Exception:
            continue

    return url_map


def _rewrite_image_urls(html: str, url_map: dict) -> str:
    """Substitui URLs absolutas de imagens por caminhos relativos images/."""
    for orig_url, local_name in url_map.items():
        html = html.replace(orig_url, f"images/{local_name}")
    return html


def _call_claude_to_build_page(html: str, screenshot_b64: str, url: str, page_type: str) -> str:
    """
    Envia HTML + screenshot para Claude gerar página no template Relívia.
    Retorna HTML gerado.
    """
    import anthropic

    api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not api_key:
        # Sem Claude API: retorna HTML original limpo
        return html

    client = anthropic.Anthropic(api_key=api_key)

    type_label = "advertorial" if page_type == "advertorial" else "landing page de produto"

    messages_content = []

    # Screenshot como imagem (se disponível)
    if screenshot_b64:
        messages_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": screenshot_b64,
            }
        })

    # HTML truncado
    html_truncado = html[:15000] if len(html) > 15000 else html

    messages_content.append({
        "type": "text",
        "text": f"""Você é um especialista em landing pages de alta conversão.

Analise esta {type_label} e recrie ela em HTML completo e limpo.

URL original: {url}

HTML original (pode estar incompleto):
```html
{html_truncado}
```

Instruções:
1. Mantenha toda a estrutura de seções, textos e argumentos de venda
2. Use CSS inline ou <style> para manter o visual similar
3. Substitua logotipos/marcas por "Relívia"
4. Mantenha as imagens referenciadas como images/nome-do-arquivo.ext
5. Retorne APENAS o HTML completo, sem explicações
6. O HTML deve ser auto-contido (sem CDN externo exceto fontes Google)
7. Botões de CTA devem ter cor #2E2BFF (azul Relívia)

Retorne somente o código HTML."""
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": messages_content}]
    )

    generated = response.content[0].text.strip()

    # Extrai HTML se vier com markdown
    if "```html" in generated:
        generated = generated.split("```html")[1].split("```")[0].strip()
    elif "```" in generated:
        generated = generated.split("```")[1].split("```")[0].strip()

    return generated


@celery.task(bind=True, name="worker.tasks.run_clone")
def run_clone(self, job_id: str, url: str, page_type: str, nome_pasta: str):
    """
    Clona uma landing page usando Crawl4AI + Claude.
    Sem dependência de scripts locais ou Chrome instalado pelo usuário.
    """
    runs_base = Path(os.environ.get("AGENTE_CLONE_RUNS_BASE", "/app/runs"))
    job_dir = runs_base / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        _update_job(job_id, status="running", progress_msg="Abrindo a página com Crawl4AI...")

        # 1. Scraping com Crawl4AI
        scraped = asyncio.run(_scrape_page(url))
        html_original = scraped["html"]
        screenshot_b64 = scraped["screenshot_b64"]
        image_urls = scraped["image_urls"]

        _update_job(job_id, progress_msg=f"Página capturada. Baixando {len(image_urls)} imagens...")

        # 2. Baixa imagens
        images_dir = job_dir / "images"
        url_map = _download_images(image_urls, images_dir, url)

        _update_job(job_id, progress_msg=f"{len(url_map)} imagens baixadas. Gerando HTML com Claude...")

        # 3. Salva screenshot
        if screenshot_b64:
            try:
                (job_dir / "screenshot.png").write_bytes(base64.b64decode(screenshot_b64))
            except Exception:
                pass

        # 4. Claude reconstrói a página no template Relívia
        html_gerado = _call_claude_to_build_page(html_original, screenshot_b64, url, page_type)

        # 5. Reescreve URLs de imagens para relativo
        html_final = _rewrite_image_urls(html_gerado, url_map)

        # 6. Injeta CSS Relívia para advertorial
        if page_type == "advertorial":
            html_final = _inject_adv_css_inline(html_final, job_dir)

        # 7. Salva index.html
        dest_html = job_dir / "index.html"
        dest_html.write_text(html_final, encoding="utf-8")

        n_images = len(list(images_dir.glob("*"))) if images_dir.exists() else 0

        _update_job(
            job_id,
            status="done",
            progress_msg=f"Concluído — {n_images} imagens baixadas",
            out_dir=str(job_dir),
            html_path=str(dest_html),
            images_count=n_images,
        )

    except Exception as e:
        _update_job(job_id, status="error", error_msg=str(e)[:1000])


def _inject_adv_css_inline(html: str, job_dir: Path) -> str:
    """Injeta CSS do template advertorial Relívia no <head>."""
    css_path = Path(__file__).parent.parent / "app" / "static" / "css" / "relivia-advertorial.css"
    if not css_path.exists():
        return html
    if "<style>" in html[:2000]:
        return html
    css = css_path.read_text(encoding="utf-8")
    return html.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
