# PRD — Araújo Deluxe (substituiu a loja Dente de Cobra no mesmo repo/Pages)

## Contexto
Usuário pediu para SUBSTITUIR a loja Dente de Cobra (repo Dente-de-macaco / GitHub Pages)
pelo site Araújo Deluxe (agendamento para lash designer), importado via zip.
Decisões: 1a substituir mesma URL · 2b tudo funcionando (backend+banco) · 3b WhatsApp depois · 4 descartar cobra.

## App: Araújo Deluxe
- Site de agendamento (cílios, sobrancelhas, unhas) com landing cinematográfica + painel admin.
- Stack: React (CRA+craco, HashRouter p/ Pages) + FastAPI + MongoDB. WhatsApp bot (Node) — adiado.
- Login admin: SÓ senha (POST /api/auth/login {password}). Seed via ADMIN_PASSWORD.

## Arquitetura de deploy (reutiliza infra da cobra)
- Frontend: GitHub Pages https://xitios660-ctrl.github.io/Dente-de-macaco/ (Actions deploy.yml)
- Backend: Render service dente-de-cobra-api (auto-redeploy do repo) -> agora roda o server.py do Araújo
- Banco: MESMO cluster Atlas (teste.xr7mji0), novo DB_NAME=araujo_deluxe
- render.yaml atualizado; requirements-deploy.txt enxuto (fastapi/motor/qrcode/pillow/etc)

## Adaptações feitas neste ambiente (Ago/2026)
- Código Araújo trazido do zip, substituindo cobra em /app
- BrowserRouter -> HashRouter; homepage=/Dente-de-macaco; api.js sanitiza barra final
- backend/.env local (DB araujo_deluxe, admin 1234, placeholders WhatsApp)
- Testado: 14/14 backend (services, business-hours, availability, booking+409, auth senha, admin protegidos) + frontend login/dashboard OK

## Pendências do usuário
- Save to GitHub (envia Araújo, republica Pages + redeploy Render)
- No Render: DB_NAME vira araujo_deluxe; admin password = ADMIN_PASSWORD atual (gugu123)
- Segurança: trocar senha GitHub + 2FA, repo privado

## Backlog
- Ativar WhatsApp bot (Node) e PIX real
- Trocar input date nativo do dashboard por Calendar shadcn
- Domínio próprio
