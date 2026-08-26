# PRD — Loja Dente de Cobra

## Problema
Loja fullstack (React + FastAPI + MongoDB) construída no Emergent, salva no GitHub
(xitios660-ctrl/Dente-de-macaco). GitHub Pages abria em branco (index.html modelo
publicado sem o build). Usuário quer a loja publicada no GitHub Pages.

## Arquitetura
- Frontend: React 19 (CRA + craco), react-router (agora HashRouter p/ Pages)
- Backend: FastAPI (server.py) — /api/shipping (ViaCEP + tabela regional),
  /api/orders, /api/auth (JWT + bloqueio 5 tentativas), /api/admin/orders
- DB: MongoDB (orders, users, login_attempts)

## Feito nesta sessão (Ago/2026)
- Trazido o código real do repo para o ambiente (era só template antes)
- SEGURANÇA: aposentada a senha exposta `cobra2026` -> nova senha admin;
  novo JWT_SECRET (openssl 32 bytes); backend/.env fora do git (.gitignore)
- Configurado para GitHub Pages:
  - `homepage` em frontend/package.json -> .../Dente-de-macaco
  - BrowserRouter -> HashRouter (rotas /admin, /rastreio funcionam no Pages)
  - Workflow .github/workflows/deploy.yml (build + deploy automatico via Actions)
  - Build validado localmente (compila para /Dente-de-macaco/)
- Testado local: login admin OK, frete CEP OK, frontend 200, loja renderiza

## Verdade / limites
- Pages = estatico. Vitrine funciona; checkout/admin/pedidos/rastreio SO funcionam
  com backend hospedado (Fase 2: Render/Railway + Atlas) + REACT_APP_BACKEND_URL.
- Agente NAO faz push nem mexe nas Settings do GitHub do usuario (conta dele).

## Backlog
- Fase 2: hospedar backend (Render/Railway) + MongoDB Atlas; setar a variavel de
  repo REACT_APP_BACKEND_URL; liberar CORS p/ https://xitios660-ctrl.github.io
- Alternativa mais simples: Deploy nativo Emergent (frontend+backend+DB em 1 URL)
