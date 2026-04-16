"""
Celery tasks — clonagem de landing pages.
Lógica: clonar igual, sem recriar. Só substituições cirúrgicas.

Fluxo:
1. Crawl4AI captura HTML completo da página
2. CSS externo → embed inline no <head>
3. Imagens:
   a. URLs relativas → absolutas
   b. Testa se carrega de outro domínio (hotlink check)
   c. Se bloqueada → converte para base64 inline
   d. Se livre → mantém URL absoluta
4. Substitui textos: produto, marca, links CTA, pixel
5. Traduz para PT-BR via Claude (só os textos, sem tocar em HTML/CSS)
6. Salva index.html autossuficiente
"""
import os
import re
import json
import base64
import asyncio
import mimetypes
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

# Domínios de tracking/analytics — ignorar imagens deles
SKIP_DOMAINS = {
    "google-analytics.com", "googletagmanager.com", "doubleclick.net",
    "facebook.com", "facebook.net", "fbcdn.net", "hotjar.com",
    "clarity.ms", "tiktok.com", "segment.com", "mixpanel.com",
    "google.com/ads", "googlesyndication.com",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _update_job(job_id: str, **kwargs):
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    kwargs["job_id"] = job_id
    with _engine.connect() as conn:
        conn.execute(text(f"UPDATE clone_jobs SET {sets} WHERE id = :job_id"), kwargs)
        conn.commit()


def _slug(text_: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", text_.lower()).strip("-")[:40]


# ─────────────────────────────────────────────────────────────
# PASSO 1: Capturar HTML completo via Crawl4AI
# ─────────────────────────────────────────────────────────────

async def _scrape_page(url: str) -> dict:
    """
    Captura o HTML completo da página com Crawl4AI (Playwright headless).
    Retorna o HTML raw, screenshot e lista de imagens encontradas.
    """
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import NoExtractionStrategy

    async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
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

    # Coleta URLs de imagens
    image_urls = []
    seen = set()

    for img in result.media.get("images", []):
        src = img.get("src", "")
        if src and src not in seen:
            seen.add(src)
            image_urls.append(src)

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


# ─────────────────────────────────────────────────────────────
# PASSO 2: CSS externo → embed inline
# ─────────────────────────────────────────────────────────────

def _embed_css(html: str, base_url: str) -> str:
    """
    Encontra <link rel="stylesheet" href="..."> e substitui pelo
    conteúdo CSS inline em <style>...</style>.
    """
    def fetch_and_embed(match):
        href = match.group(1)
        if href.startswith("data:"):
            return match.group(0)
        abs_href = urljoin(base_url, href)
        try:
            resp = requests.get(abs_href, headers=HEADERS, timeout=10)
            if resp.status_code == 200 and "text/css" in resp.headers.get("content-type", ""):
                css_content = resp.text
                # Corrige URLs relativas dentro do CSS
                css_content = re.sub(
                    r'url\(["\']?(?!data:|http|//)([^)"\']+)["\']?\)',
                    lambda m: f'url({urljoin(abs_href, m.group(1))})',
                    css_content
                )
                return f"<style>\n{css_content}\n</style>"
        except Exception:
            pass
        return match.group(0)  # fallback: mantém o link original

    html = re.sub(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\'][^>]*>',
        fetch_and_embed,
        html,
        flags=re.IGNORECASE,
    )
    # Também tenta o formato com href antes de rel
    html = re.sub(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\'][^>]*>',
        fetch_and_embed,
        html,
        flags=re.IGNORECASE,
    )
    return html


# ─────────────────────────────────────────────────────────────
# PASSO 3: Imagens — 3 estratégias
# ─────────────────────────────────────────────────────────────

def _make_absolute_urls(html: str, base_url: str) -> str:
    """
    Estratégia A: converte todas as URLs relativas de imagens para absolutas.
    Ex: /images/foto.jpg → https://site.com/images/foto.jpg
    """
    def fix_src(match):
        prefix = match.group(1)  # src=" ou src='
        src = match.group(2)
        quote = match.group(3)
        if src.startswith("data:") or src.startswith("http"):
            return f"{prefix}{src}{quote}"
        abs_src = urljoin(base_url, src)
        return f"{prefix}{abs_src}{quote}"

    # src="..." e src='...'
    html = re.sub(r'(src=["\'])([^"\']+)(["\'])', fix_src, html)
    # srcset
    def fix_srcset(match):
        srcset = match.group(2)
        parts = []
        for part in srcset.split(","):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            if tokens and not tokens[0].startswith("http") and not tokens[0].startswith("data:"):
                tokens[0] = urljoin(base_url, tokens[0])
            parts.append(" ".join(tokens))
        return match.group(1) + ", ".join(parts) + match.group(3)

    html = re.sub(r'(srcset=["\'])([^"\']+)(["\'])', fix_srcset, html)
    return html


def _is_hotlink_blocked(img_url: str, base_url: str) -> bool:
    """
    Estratégia B: testa se a imagem bloqueia quando carregada de outro domínio.
    Faz um HEAD com Referer diferente do original.
    """
    try:
        parsed_base = urlparse(base_url)
        fake_referer = f"https://meusite.com.br/"
        resp = requests.head(
            img_url,
            headers={**HEADERS, "Referer": fake_referer},
            timeout=8,
            allow_redirects=True,
        )
        # 403 ou 401 = hotlink bloqueado
        return resp.status_code in (401, 403)
    except Exception:
        return False


def _img_to_base64(img_url: str, base_url: str) -> str | None:
    """
    Estratégia C: baixa a imagem com Referer correto e converte para base64 inline.
    Retorna string data:image/...;base64,... ou None se falhar.
    """
    try:
        resp = requests.get(
            img_url,
            headers={**HEADERS, "Referer": base_url},
            timeout=15,
            stream=True,
        )
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"

        img_bytes = resp.content
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:{content_type};base64,{b64}"
    except Exception:
        return None


def _resolve_images(html: str, base_url: str, progress_cb=None) -> str:
    """
    Aplica as 3 estratégias de imagem em sequência:
    A → URLs relativas para absolutas (sempre)
    B → Detecta hotlink
    C → Converte bloqueadas para base64
    """
    # A: absolutas
    html = _make_absolute_urls(html, base_url)

    # Encontra todas as imagens absolutas no HTML
    img_urls = list(set(re.findall(r'src=["\']+(https?://[^"\']+)["\']', html)))

    total = len(img_urls)
    convertidos = 0

    for i, img_url in enumerate(img_urls):
        # Pula domínios de tracking
        parsed = urlparse(img_url)
        if any(d in parsed.netloc for d in SKIP_DOMAINS):
            continue
        # Pula SVG e data URIs
        if img_url.endswith(".svg") or img_url.startswith("data:"):
            continue

        # B: testa hotlink
        if _is_hotlink_blocked(img_url, base_url):
            # C: converte para base64
            b64_src = _img_to_base64(img_url, base_url)
            if b64_src:
                html = html.replace(img_url, b64_src)
                convertidos += 1

        if progress_cb and i % 5 == 0:
            progress_cb(f"Processando imagens... {i+1}/{total}")

    return html


# ─────────────────────────────────────────────────────────────
# PASSO 4: Substituições cirúrgicas (produto, marca, links, pixel)
# ─────────────────────────────────────────────────────────────

def _apply_substitutions(html: str, subs: dict) -> str:
    """
    Aplica substituições apenas em nós de texto — não toca em atributos
    HTML, CSS, classes, IDs ou scripts (exceto pixel).

    subs = {
        "produto_original": "Meu Produto",
        "marca_original": "Minha Marca",
        "link_cta": "https://meusite.com/comprar",
        "pixel_id": "123456789",
        "preco_original": "R$197",
        "preco_novo": "R$97",
        "medico_original": "Dr. James",
        "medico_novo": "Dr. Carlos",
    }
    """
    # Troca produto e marca (case-insensitive, em textos visíveis)
    for key in ["produto_original", "marca_original", "medico_original"]:
        novo_key = key.replace("_original", "_novo")
        if subs.get(key) and subs.get(novo_key):
            old = subs[key]
            new = subs[novo_key]
            # Substitui variações de case
            html = html.replace(old, new)
            html = html.replace(old.upper(), new.upper())
            html = html.replace(old.title(), new.title())

    # Troca links dos botões CTA
    if subs.get("link_cta"):
        # Encontra todos os hrefs de botões/links CTA
        # Heurística: links com texto contendo palavras de compra
        cta_keywords = r'(comprar|buy|order|get|purchase|checkout|garantir|quero|claim|shop)'

        def replace_cta_href(match):
            full_tag = match.group(0)
            if re.search(cta_keywords, full_tag, re.IGNORECASE):
                return re.sub(r'href=["\'][^"\']+["\']', f'href="{subs["link_cta"]}"', full_tag)
            return full_tag

        html = re.sub(r'<a[^>]+href=["\'][^"\']+["\'][^>]*>', replace_cta_href, html, flags=re.IGNORECASE)

        # Também botões com onclick
        html = re.sub(
            r"(window\.location(?:\.href)?\s*=\s*['\"])[^'\"]+(['\"])",
            lambda m: m.group(1) + subs["link_cta"] + m.group(2),
            html
        )

    # Troca Pixel Meta
    if subs.get("pixel_id"):
        html = re.sub(
            r"fbq\('init',\s*['\"](\d+)['\"]",
            f"fbq('init', '{subs['pixel_id']}'",
            html
        )
        html = re.sub(
            r"(\"pixel_id\"\s*:\s*\")(\d+)(\")",
            lambda m: m.group(1) + subs["pixel_id"] + m.group(3),
            html
        )

    # Troca preços
    if subs.get("preco_original") and subs.get("preco_novo"):
        html = html.replace(subs["preco_original"], subs["preco_novo"])

    # Remove scripts de analytics do concorrente (mantém Meta Pixel)
    html = re.sub(
        r'<script[^>]*>(.*?google-analytics.*?|.*?gtag\(.*?|.*?hotjar.*?|.*?clarity.*?)</script>',
        '',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    return html


# ─────────────────────────────────────────────────────────────
# PASSO 5: Tradução via Claude (só textos, não toca em HTML/CSS)
# ─────────────────────────────────────────────────────────────

def _translate_to_ptbr(html: str, url: str) -> str:
    """
    Usa Claude para traduzir os textos visíveis para PT-BR.
    Instrução explícita: não alterar HTML, CSS, atributos, scripts.
    Só traduz nós de texto.
    """
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not api_key:
        return html

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Trunca HTML para não estourar contexto
    html_input = html[:40000] if len(html) > 40000 else html

    prompt = f"""Você receberá o HTML de uma landing page em inglês (ou outro idioma).

Sua tarefa: traduzir APENAS os textos visíveis para Português Brasileiro natural e persuasivo.

REGRAS ABSOLUTAS — NUNCA violar:
- NÃO alterar nenhuma tag HTML (<div>, <span>, <p>, etc.)
- NÃO alterar atributos HTML (class, id, style, data-*, href, src)
- NÃO alterar nenhuma linha de CSS
- NÃO alterar scripts JavaScript
- NÃO alterar URLs de imagens
- NÃO alterar nomes de arquivos
- APENAS traduzir o texto dentro dos nós: entre > e <

Adaptações obrigatórias ao traduzir:
- FDA → ANVISA
- USD/$ → R$ (Reais)
- Cidades americanas → cidades brasileiras (São Paulo, Rio, Curitiba, etc.)
- "Medicare", "insurance" → "plano de saúde"
- Datas → formato brasileiro (DD de mês de AAAA)
- Manter tom persuasivo e emocional do original

Retorne APENAS o HTML com os textos traduzidos. Sem explicações. Sem markdown.

HTML:
{html_input}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    translated = response.content[0].text.strip()

    # Remove markdown se vier com ```
    if "```html" in translated:
        translated = translated.split("```html")[1].split("```")[0].strip()
    elif "```" in translated:
        translated = translated.split("```")[1].split("```")[0].strip()

    return translated


# ─────────────────────────────────────────────────────────────
# TASK PRINCIPAL
# ─────────────────────────────────────────────────────────────

@celery.task(bind=True, name="worker.tasks.run_clone")
def run_clone(self, job_id: str, url: str, page_type: str, nome_pasta: str):
    """
    Clona uma landing page — clonar igual, não recriar.

    Fluxo:
    1. Crawl4AI captura HTML completo
    2. CSS externo → embed inline
    3. Imagens: relativas→absolutas, hotlink→base64
    4. Substituições cirúrgicas (produto, marca, links, pixel)
    5. Tradução PT-BR via Claude (só textos)
    6. Salva index.html autossuficiente
    """
    runs_base = Path(os.environ.get("AGENTE_CLONE_RUNS_BASE", "/app/runs"))
    job_dir = runs_base / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── 1. Scraping ──────────────────────────────────────
        _update_job(job_id, status="running", progress_msg="Abrindo a página com Crawl4AI...")
        scraped = asyncio.run(_scrape_page(url))
        html = scraped["html"]

        if not html:
            raise RuntimeError("HTML capturado está vazio")

        # Salva screenshot
        if scraped["screenshot_b64"]:
            try:
                (job_dir / "screenshot.png").write_bytes(
                    base64.b64decode(scraped["screenshot_b64"])
                )
            except Exception:
                pass

        # ── 2. CSS externo → inline ──────────────────────────
        _update_job(job_id, progress_msg="Incorporando CSS externo...")
        html = _embed_css(html, url)

        # ── 3. Imagens ───────────────────────────────────────
        _update_job(job_id, progress_msg="Processando imagens...")

        def img_progress(msg):
            _update_job(job_id, progress_msg=msg)

        html = _resolve_images(html, url, progress_cb=img_progress)

        # ── 4. Substituições ─────────────────────────────────
        _update_job(job_id, progress_msg="Aplicando substituições...")

        # Lê substituições salvas no job (se houver)
        subs_path = job_dir / "substitutions.json"
        subs = {}
        if subs_path.exists():
            try:
                subs = json.loads(subs_path.read_text())
            except Exception:
                pass

        if subs:
            html = _apply_substitutions(html, subs)

        # ── 5. Tradução PT-BR ────────────────────────────────
        _update_job(job_id, progress_msg="Traduzindo para PT-BR...")
        html = _translate_to_ptbr(html, url)

        # ── 6. Salva ─────────────────────────────────────────
        dest_html = job_dir / "index.html"
        dest_html.write_text(html, encoding="utf-8")

        _update_job(
            job_id,
            status="done",
            progress_msg="Clonagem concluída",
            out_dir=str(job_dir),
            html_path=str(dest_html),
            images_count=0,
        )

    except Exception as e:
        _update_job(job_id, status="error", error_msg=str(e)[:1000])
