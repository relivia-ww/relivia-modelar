# Story 1.1.0 — Clonar URL e gerar HTML funcional

## Status: In Progress

---

## Objetivo

O usuário cola uma URL no formulário, clica em clonar, e recebe um arquivo `index.html` autossuficiente que:
- Tem o mesmo layout visual da página original
- Tem todas as imagens no lugar certo
- Funciona em qualquer servidor sem dependências externas
- Pode ser aberto diretamente no browser e parecer idêntico ao original

---

## Critérios de aceitação

- [x] Usuário consegue submeter uma URL em `/modelar`
- [x] Job é criado no banco com status `queued`
- [x] Celery processa o job e atualiza o status em tempo real
- [x] Pipeline completa sem erro para uma página simples
- [ ] `index.html` gerado carrega no browser com layout preservado
- [ ] CSS está inline no `<head>` (sem dependências externas de stylesheet)
- [ ] Imagens carregam (absolutas ou base64)
- [x] Status final é `done` no dashboard

---

## O que já existe

| Componente | Estado |
|-----------|--------|
| `worker/tasks.py` | Escrito — pipeline de 6 etapas implementado |
| `app/routes/modelar.py` | Escrito — cria job e enfileira Celery |
| `app/templates/modelar.html` | Existe — formulário de URL |
| `app/templates/modelar_status.html` | Existe — polling de status |
| Dockerfile | OK — playwright:v1.58.0-jammy |
| Railway | Deploy SUCCESS — `https://web-production-206b62.up.railway.app` |

---

## O que precisa ser verificado e corrigido

### Tarefa 1 — Testar o pipeline ponta a ponta

- [x] Fazer login no dashboard
- [x] Submeter uma URL simples (example.com) — falhou com `No module named 'anthropic'`
- [x] Submeter URL real (tryemsense.com) — falhou com créditos Anthropic zerados
- [x] Fix: `anthropic>=0.40.0` adicionado ao `requirements.txt`
- [x] Fix: tradução PT-BR com try/except — fallback sem traduzir se API falhar
- [x] Submeter URL real novamente — job retornou `done` ✅
- [ ] Abrir o `index.html` gerado e verificar visualmente

### Tarefa 2 — Verificar Crawl4AI no Railway

- [x] Crawl4AI + Playwright funcionando no container — confirmado via teste real
- [x] Chromium abre sem erro — chegou até etapa de tradução em todos os testes

### Tarefa 3 — Verificar pipeline CSS

- [ ] Confirmar visualmente que CSS está inline no HTML gerado

### Tarefa 4 — Verificar pipeline de imagens

- [ ] Confirmar visualmente que imagens carregam no HTML gerado

### Tarefa 5 — Verificar tradução PT-BR

- [x] `CLAUDE_API_KEY` configurada no Railway
- [x] Crédito adicionado à conta Anthropic
- [x] Fallback implementado — se API falhar, retorna HTML sem traduzir
- [ ] Verificar se tradução foi aplicada no job `ab09aa9c`

### Tarefa 6 — Expor o HTML gerado

- [x] Rota `/modelar/<job_id>/download` criada em `app/routes/modelar.py`
- [ ] Adicionar botão "Baixar HTML" na tela de status quando `status == done`

---

## Dev Notes

### Localização dos arquivos gerados
```
/app/runs/<job_id>/
├── index.html      ← HTML autossuficiente
└── screenshot.png  ← screenshot da página original
```

### Como ver logs no Railway
```bash
# Via API GraphQL — não há CLI direto
# Verificar no painel: railway.app → projeto → web → Deployments → logs
```

### Variáveis obrigatórias no Railway
```
CLAUDE_API_KEY     ← para tradução PT-BR
REDIS_URL          ← broker Celery
DATABASE_URL       ← PostgreSQL
AGENTE_CLONE_RUNS_BASE=/app/runs
PORT=5050
```

### Erro mais provável
Crawl4AI instalando Playwright mas o executável do Chromium não estar no path correto dentro do container. Se ocorrer:
```dockerfile
RUN pip install --no-cache-dir -r requirements.txt gunicorn && \
    playwright install chromium && \
    apt-get update && apt-get install -y supervisor && \
    rm -rf /var/lib/apt/lists/*
```

---

## Dev Agent Record

### Checklist
- [x] Tarefa 1 — Pipeline testado ponta a ponta
- [x] Tarefa 2 — Crawl4AI/Playwright funcionando no Railway
- [ ] Tarefa 3 — CSS inline confirmado visualmente
- [ ] Tarefa 4 — Imagens confirmadas visualmente
- [x] Tarefa 5 — Tradução PT-BR com fallback implementado
- [x] Tarefa 6 — Rota de download criada

### Debug Log
- `example.com` → erro `No module named 'anthropic'` → fix: adicionado ao requirements.txt
- `tryemsense.com` → erro `credit balance too low` → fix: try/except na tradução + crédito adicionado
- `tryemsense.com` (2ª tentativa) → `done` ✅ — job `ab09aa9c`
- `rejuvacare.com.br` → erro `ERR_NAME_NOT_RESOLVED` — domínio inacessível pelo Railway

### Completion Notes
- Pendente: verificação visual do HTML gerado (CSS + imagens)
- Pendente: botão de download na tela de status

### Change Log
- `requirements.txt` — adicionado `anthropic>=0.40.0`
- `worker/tasks.py` — tradução com try/except fallback
- `app/routes/modelar.py` — rota `/download` adicionada
- `Dockerfile` — removido `ARG CACHEBUST` (restaura layer cache)
