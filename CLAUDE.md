# CLAUDE.md — relivia-modelar

## O que é este projeto

SaaS Flask que clona landing pages de concorrentes. O usuário cola uma URL, o sistema captura a página completa e entrega um HTML autossuficiente pronto para subir no próprio domínio.

Filosofia central: **clonar igual, não recriar**. O HTML original é mantido intacto. Só substituições cirúrgicas em texto — nunca CSS, nunca estrutura, nunca atributos HTML.

---

## Stack

- **Web**: Flask 3 + Gunicorn (2 workers, porta 5050)
- **Worker**: Celery 5 com concurrency=1
- **Process manager**: supervisord — roda web + worker no mesmo container
- **Fila**: Redis
- **Banco**: PostgreSQL (produção) / SQLite (dev local)
- **Scraping**: Crawl4AI + Playwright (Chromium headless)
- **Tradução**: Claude API (claude-sonnet-4-6)
- **Imagens IA**: Gemini API
- **Deploy**: Railway (container Docker único)
- **Publicação de páginas**: Vercel API

---

## Infraestrutura Railway

| Serviço | ID | Descrição |
|---------|-----|-----------|
| web | `48e87044-2d6d-45b5-9202-2b9c168ecf06` | Flask + Celery via supervisord |
| redis | `b08a7c72-c57b-46ce-903c-50c17248ac15` | Broker Celery |
| postgres | `f2b13ac2-b28a-46be-8391-cb9eb4c7c5db` | Banco principal |

- **URL pública**: `https://web-production-206b62.up.railway.app`
- **Project ID**: `518161c8-62c4-42b9-9678-f9de5d69f1b3`
- **Environment ID**: `924fce94-4425-4746-8251-f33261520e48`
- **Repo**: `relivia-ww/relivia-modelar`

---

## Dockerfile — regras críticas

- **Imagem base**: `mcr.microsoft.com/playwright/python:v1.58.0-jammy` — não trocar
- **Ordem obrigatória**: `COPY requirements.txt` → `RUN pip install` → `COPY . .`
- **Nunca adicionar `ARG CACHEBUST`** — quebra o layer cache e causa builds de 8 min
- Com a ordem correta, push de código = build em ~30-60s (pip install fica em cache)
- O pip install só rebuilda quando `requirements.txt` mudar

---

## Pipeline de clonagem (worker/tasks.py)

Fluxo do `run_clone()` em 6 etapas:

1. **Scraping** — Crawl4AI abre Chromium headless, captura HTML completo + screenshot
2. **CSS** — `_embed_css()`: baixa todos os `<link rel="stylesheet">` externos e embute inline no `<head>`
3. **Imagens** — `_resolve_images()`: 3 estratégias em sequência:
   - A: URLs relativas → absolutas
   - B: `_is_hotlink_blocked()`: HEAD request com Referer falso detecta bloqueio
   - C: `_img_to_base64()`: imagens bloqueadas → base64 inline
4. **Substituições** — `_apply_substitutions()`: produto, marca, links CTA, pixel Meta — só nós de texto
5. **Tradução** — `_translate_to_ptbr()`: Claude traduz textos visíveis para PT-BR (nunca HTML/CSS/scripts)
6. **Salva** — `index.html` autossuficiente em `/app/runs/<job_id>/`

Substituições lidas de `substitutions.json` na pasta do job (precisa de UI — ver pendências).

---

## Estrutura de arquivos

```
relivia-modelar/
├── app/
│   ├── __init__.py         ← cria Flask app, registra blueprints
│   ├── config.py           ← configs por ambiente (dev/prod)
│   ├── extensions.py       ← SQLAlchemy + LoginManager
│   ├── models/
│   │   ├── clone_job.py    ← tabela de jobs (status, progress, output)
│   │   ├── user.py         ← usuários com auth
│   │   └── integration.py  ← tokens GitHub/Vercel por usuário
│   ├── routes/
│   │   ├── auth.py         ← login/register/logout
│   │   ├── modelar.py      ← criar job, ver status, deletar
│   │   ├── editor.py       ← editar HTML gerado
│   │   ├── publicar.py     ← publicar no Vercel
│   │   └── onboarding.py   ← configurar GitHub/Vercel tokens
│   ├── services/
│   │   ├── vercel_service.py  ← deploy via Vercel API
│   │   └── gemini_service.py  ← geração de imagens
│   └── templates/          ← HTML Jinja2
├── worker/
│   ├── celery_app.py       ← instância Celery + config Redis
│   └── tasks.py            ← toda a lógica de clonagem
├── Dockerfile              ← playwright:v1.58.0-jammy → pip → código
├── supervisord.conf        ← gunicorn + celery juntos no mesmo container
├── railway.toml            ← só [build] e [deploy], sem startCommand
└── requirements.txt        ← Flask, Celery, Crawl4AI, Anthropic...
```

---

## Fluxo do usuário

1. Acessa `/modelar` → cola URL + nome da pasta
2. Flask cria `CloneJob` no banco com status `queued`
3. `run_clone.delay(...)` enfileira no Redis
4. Redireciona para `/modelar/<job_id>` — polling em `status.json` a cada 2s
5. Celery executa pipeline de 6 etapas
6. Status vira `done` → usuário acessa o HTML gerado

---

## Pendências conhecidas

- **UI de substituições**: formulário na tela de modelar para coletar produto, marca, link CTA, pixel antes de clonar (hoje precisa criar `substitutions.json` manualmente)
- **Download do resultado**: botão para baixar o `index.html` gerado
- **Editor visual**: `editor.py` existe mas não conecta com o arquivo gerado
- **Publicar no Vercel**: `publicar.py` e `vercel_service.py` existem mas fluxo completo não testado

---

## Variáveis de ambiente necessárias

```
SECRET_KEY
CLAUDE_API_KEY
GEMINI_API_KEY
GITHUB_TOKEN
GITHUB_REPO
GITHUB_BRANCH
VERCEL_TOKEN
VERCEL_PROJECT_ID
VERCEL_DOMAIN
AGENTE_CLONE_RUNS_BASE=/app/runs
PORT=5050
REDIS_URL=redis://redis.railway.internal:6379
DATABASE_URL=postgresql+psycopg2://...
```

---

## Regras de desenvolvimento

- Nunca adicionar `CACHEBUST` ao Dockerfile
- Nunca inverter a ordem `requirements.txt` → `pip install` → `COPY . .`
- Nunca recriar HTML do zero — sempre clonar e fazer substituições cirúrgicas
- `_translate_to_ptbr()` só traduz texto entre tags, nunca atributos ou CSS
- Commits vão para `main` e disparam redeploy automático no Railway
