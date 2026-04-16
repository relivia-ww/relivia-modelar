# Story 1.1.0 — Clonar URL e gerar HTML funcional

## Status: Ready for Dev

---

## Objetivo

O usuário cola uma URL no formulário, clica em clonar, e recebe um arquivo `index.html` autossuficiente que:
- Tem o mesmo layout visual da página original
- Tem todas as imagens no lugar certo
- Funciona em qualquer servidor sem dependências externas
- Pode ser aberto diretamente no browser e parecer idêntico ao original

---

## Critérios de aceitação

- [ ] Usuário consegue submeter uma URL em `/modelar`
- [ ] Job é criado no banco com status `queued`
- [ ] Celery processa o job e atualiza o status em tempo real
- [ ] Pipeline completa sem erro para uma página simples
- [ ] `index.html` gerado carrega no browser com layout preservado
- [ ] CSS está inline no `<head>` (sem dependências externas de stylesheet)
- [ ] Imagens carregam (absolutas ou base64)
- [ ] Status final é `done` no dashboard

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

- [ ] Fazer login no dashboard
- [ ] Submeter uma URL simples (ex: uma landing page pública)
- [ ] Acompanhar o job até `done` ou `error`
- [ ] Se `error`: ler `error_msg` e corrigir
- [ ] Se `done`: abrir o `index.html` gerado e verificar visualmente

### Tarefa 2 — Verificar Crawl4AI no Railway

- [ ] Confirmar que Crawl4AI consegue rodar Playwright no container
- [ ] Verificar nos logs do Railway se o Chromium abre sem erro
- [ ] Erro comum: `BrowserType.launch: Executable doesn't exist` — se ocorrer, rodar `playwright install chromium` no Dockerfile

### Tarefa 3 — Verificar pipeline CSS

- [ ] Confirmar que `_embed_css()` está baixando e embutindo os stylesheets
- [ ] Se o HTML gerado tiver `<link rel="stylesheet">` ainda apontando para o domínio original, a função está falhando
- [ ] Fix: verificar timeout e content-type na resposta do requests.get

### Tarefa 4 — Verificar pipeline de imagens

- [ ] Confirmar que URLs relativas foram convertidas para absolutas
- [ ] Confirmar que imagens com hotlink protection viraram base64
- [ ] Se imagens quebrarem no HTML gerado: inspecionar src no arquivo gerado

### Tarefa 5 — Verificar tradução PT-BR

- [ ] Confirmar que `CLAUDE_API_KEY` está configurada no Railway
- [ ] Se a variável não existir, `_translate_to_ptbr()` retorna o HTML sem traduzir (comportamento correto — não quebra)
- [ ] Verificar se Claude está recebendo e retornando HTML válido (não markdown)

### Tarefa 6 — Expor o HTML gerado

- [ ] Depois que job está `done`, o usuário precisa conseguir ver/baixar o resultado
- [ ] Adicionar rota `/modelar/<job_id>/download` que serve o `index.html` gerado
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
- [ ] Tarefa 1 — Pipeline testado ponta a ponta
- [ ] Tarefa 2 — Crawl4AI/Playwright funcionando no Railway
- [ ] Tarefa 3 — CSS inline funcionando
- [ ] Tarefa 4 — Imagens funcionando
- [ ] Tarefa 5 — Tradução PT-BR funcionando
- [ ] Tarefa 6 — Rota de download criada

### Debug Log
_(preencher durante implementação)_

### Completion Notes
_(preencher ao concluir)_

### Change Log
_(preencher com arquivos modificados)_
