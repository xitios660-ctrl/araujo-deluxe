# PRD — Loja Dente de Cobra

## Problema
Loja fullstack (React + FastAPI + MongoDB) construída no Emergent, salva no GitHub
(xitios660-ctrl/Dente-de-macaco). GitHub Pages abria em branco. Objetivo: loja
publicada e FUNCIONANDO no GitHub Pages.

## Arquitetura FINAL (no ar)
- Frontend: React (CRA+craco), HashRouter -> GitHub Pages
  URL: https://xitios660-ctrl.github.io/Dente-de-macaco/
  Publicação automática via GitHub Actions (.github/workflows/deploy.yml)
- Backend: FastAPI no Render (free) -> https://dente-de-cobra-api.onrender.com
  Configurado por render.yaml (Blueprint) + backend/requirements-deploy.txt
- DB: MongoDB Atlas M0 (cluster teste.xr7mji0), user "Dente"
- Ligação: repo variable REACT_APP_BACKEND_URL (Actions) apontando pro Render

## Feito (Ago/2026)
- Código real trazido do repo (era template antes)
- SEGURANÇA: senha exposta `cobra2026` aposentada; novo JWT
- Pages: homepage + HashRouter + workflow Actions (build/deploy automatico)
- Admin: persistencia de login via localStorage (funciona cross-domain Pages<->Render)
- Fase 2 concluida: Atlas + Render + variavel + rebuild
- TESTADO NO AR: API health OK, login admin OK (gugu123), frete/CEP OK,
  checkout cria pedido (DDC-5D8273 salvo no Atlas), /admin lista pedidos, tela de
  login /admin renderiza no Pages

## Credenciais admin
- admin@dentedecobra.com / gugu123 (definida no Render como ADMIN_PASSWORD)

## Observacoes / limites
- Render free "dorme" apos ~15min -> 1a requisicao demora ~50s (normal)
- Pendencias de seguranca do USUARIO: trocar senha GitHub + 2FA, deixar repo privado

## Backlog / futuro
- Upgrade Render para instancia que nao dorme (opcional)
- Dominio proprio para a loja
- Features do backlog: desconto PIX, cupom, codigo de rastreio Correios, filtro de pedidos
