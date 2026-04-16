# Story 0.1.0 — Visão Geral do Projeto relivia-modelar

## Status: Reference

---

## O que é

O **relivia-modelar** é um SaaS Flask que permite clonar landing pages de concorrentes com um clique. O usuário cola a URL de uma página que quer copiar, o sistema captura tudo (HTML, CSS, imagens) e entrega um arquivo HTML autossuficiente pronto para subir no próprio domínio.

---

## Problema que resolve

Criar landing pages e advertoriais do zero é lento e caro. As páginas que já convertem existem — estão nos concorrentes. O relivia-modelar permite capturar essas páginas exatamente como são, traduzir para PT-BR, trocar produto/marca/links e publicar como se fosse própria.

---

## Filosofia central

**Clonar igual, não recriar.**

- O HTML original é mantido 100% intacto
- CSS nunca é alterado
- Imagens ficam nas posições originais
- Só substituições cirúrgicas em nós de texto (produto, marca, links, pixel)
- Tradução PT-BR via Claude — só o texto visível, nunca atributos ou scripts

---

## Usuário-alvo

Donos de negócios digitais (e-commerce, infoprodutos, suplementos) que querem lançar produtos rapidamente usando páginas já validadas pelo mercado como base.

---

## Fluxo principal

```
1. Usuário faz login
2. Configura integração GitHub/Vercel (onboarding)
3. Acessa /modelar → cola URL da página do concorrente
4. Preenche: nome da pasta, tipo (produto/advertorial)
5. Preenche substituições: produto, marca, link CTA, pixel Meta
6. Sistema clona a página em background (Celery + Crawl4AI)
7. Usuário acompanha progresso em tempo real
8. HTML gerado fica disponível para download e edição
9. Usuário publica direto no Vercel com 1 clique
```

---

## Pipeline de clonagem (worker/tasks.py)

| Etapa | Função | O que faz |
|-------|--------|-----------|
| 1 | `_scrape_page()` | Crawl4AI + Playwright captura HTML completo + screenshot |
| 2 | `_embed_css()` | CSS externo → inline no `<head>` |
| 3 | `_resolve_images()` | Relativas→absolutas → hotlink check → base64 |
| 4 | `_apply_substitutions()` | Troca produto, marca, links CTA, pixel |
| 5 | `_translate_to_ptbr()` | Claude traduz textos visíveis para PT-BR |
| 6 | Salva | `index.html` autossuficiente em `/app/runs/<job_id>/` |

---

## Stack técnica

| Camada | Tecnologia |
|--------|-----------|
| Web | Flask 3 + Gunicorn |
| Worker | Celery 5 + Redis |
| Process manager | supervisord (web + worker no mesmo container) |
| Scraping | Crawl4AI + Playwright (Chromium headless) |
| Tradução | Claude API (claude-sonnet-4-6) |
| Banco | PostgreSQL (prod) / SQLite (dev) |
| Deploy | Railway (container Docker único) |
| Publicação | Vercel API |

---

## Módulos do projeto

| Arquivo | Responsabilidade |
|---------|-----------------|
| `app/routes/auth.py` | Login, register, logout |
| `app/routes/modelar.py` | Criar job, ver status, deletar |
| `app/routes/editor.py` | Editar HTML gerado |
| `app/routes/publicar.py` | Publicar no Vercel |
| `app/routes/onboarding.py` | Configurar GitHub/Vercel tokens |
| `app/models/clone_job.py` | Modelo do job de clonagem |
| `app/models/user.py` | Usuário com auth |
| `app/models/integration.py` | Tokens por usuário |
| `app/services/vercel_service.py` | Deploy via Vercel API |
| `app/services/gemini_service.py` | Geração de imagens |
| `worker/tasks.py` | Pipeline completo de clonagem |

---

## Pendências (stories seguintes)

| Story | Feature |
|-------|---------|
| 1.1.0 | UI de substituições — formulário antes de clonar |
| 1.2.0 | Download do HTML gerado |
| 1.3.0 | Editor visual conectado ao arquivo gerado |
| 1.4.0 | Publicar no Vercel — fluxo completo |

---

## Dev Notes

- Nunca adicionar `ARG CACHEBUST` ao Dockerfile — quebra layer cache (8 min de build)
- Ordem obrigatória no Dockerfile: `COPY requirements.txt` → `pip install` → `COPY . .`
- `substitutions.json` lido da pasta do job — precisa ser criado pela UI (story 1.1.0)
- Railway redeploy automático a cada push para `main`
