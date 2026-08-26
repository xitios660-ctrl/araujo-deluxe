# Guia de Deploy — Loja "Dente de Cobra" no GitHub Pages

> Execute tudo no SEU PC, dentro do repositório clonado `Dente-de-macaco`.
> O código da loja está no seu GitHub, não no ambiente Emergent.

---

## 🚨 FASE 0 — Segurança (faça AGORA, antes de tudo)

Seu repositório é **público** e vazou credenciais em commits/README/memory.

1. Troque a senha do **GitHub** e ative **2FA**.
2. Deixe o repo **privado**: GitHub → repo → Settings → General → "Change repository visibility" → Private. (O Pages continua funcionando.)
3. Troque a senha do admin (`cobra2026` está exposta) e gere um novo `JWT_SECRET`.
4. Garanta que `backend/.env` está no `.gitignore` e NÃO commitado:
   ```bash
   git rm --cached backend/.env 2>/dev/null
   echo "backend/.env" >> .gitignore
   ```

---

## 🟢 FASE 1 — Fazer a loja APARECER (tela branca → site)

### 1.1 Remova a gambiarra
```bash
git rm index.html
git rm frontend/Gh
git commit -m "Remove index.html manual e arquivo Gh (o build gera o site)"
```

### 1.2 Configure o caminho base no `frontend/package.json`
Adicione a linha `"homepage"` logo depois de `"private": true,`:
```json
  "private": true,
  "homepage": "https://xitios660-ctrl.github.io/Dente-de-macaco",
```

### 1.3 ⚠️ CORREÇÃO CRÍTICA — Roteamento SPA em subcaminho
Sua loja usa `BrowserRouter` do react-router. Em subcaminho do GitHub Pages,
`/admin` e `/rastreio` dariam **404 ou tela branca** mesmo com o build correto.

**Opção A (mais robusta — recomendada): trocar para HashRouter**
No `frontend/src/App.js` (ou onde estiver o Router), troque:
```jsx
import { BrowserRouter } from "react-router-dom";
// ...
<BrowserRouter>
```
por:
```jsx
import { HashRouter } from "react-router-dom";
// ...
<HashRouter>
```
As URLs ficam tipo `.../Dente-de-macaco/#/admin` — funcionam 100% no Pages,
sem precisar de 404.html.

**Opção B (mantém URLs limpas): BrowserRouter com basename + 404.html**
- No Router: `<BrowserRouter basename={process.env.PUBLIC_URL}>`
- Depois do build, copie o index como 404 (passo 1.6).
- Adicione o script do spa-github-pages no `index.html` e `404.html`
  (veja https://github.com/rafgraph/spa-github-pages).

👉 Se quer o caminho sem dor de cabeça, use a **Opção A**.

### 1.4 Instale e compile
```bash
cd frontend
npm install
npm run build
```
Gera a pasta `frontend/build` com o site real (scripts incluídos).

### 1.5 Publique com gh-pages
```bash
npm install -D gh-pages
npx gh-pages -d build
```
Isso cria/atualiza a branch `gh-pages`.

### 1.6 (Só se escolheu a Opção B) 404 para SPA
Antes de publicar, copie o index como 404:
```bash
cp build/index.html build/404.html
npx gh-pages -d build
```
(Na Opção A com HashRouter, PULE este passo.)

### 1.7 Ative o Pages
GitHub → repo → **Settings → Pages**:
- Source: **Deploy from a branch**
- Branch: **gh-pages** / **/(root)** → **Save**

Aguarde 1–2 min e abra:
`https://xitios660-ctrl.github.io/Dente-de-macaco/`

✅ **Resultado:** loja visível e navegável.
⚠️ Checkout, /admin, pedidos e rastreio ainda NÃO respondem — normal, falta a Fase 2.

---

## 🔵 FASE 2 — Backend + Banco (fazer FUNCIONAR de verdade)

O Pages não roda Python. FastAPI + MongoDB precisam de host próprio.

### 2.1 Banco — MongoDB Atlas (grátis)
1. Crie conta em https://www.mongodb.com/cloud/atlas → cluster **M0** (free).
2. Database Access → crie usuário/senha.
3. Network Access → libere `0.0.0.0/0` (ou o IP do host).
4. Copie a **connection string** (`MONGO_URL`), algo como:
   `mongodb+srv://user:senha@cluster.xxxx.mongodb.net/?retryWrites=true&w=majority`

### 2.2 Backend — Render (mais simples)
1. https://render.com → New → **Web Service** → conecte o repo.
2. Configurações:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
     (ajuste `server:app` se o arquivo/variável tiver outro nome)
3. **Environment Variables** (Render → Environment):
   - `MONGO_URL` = string do Atlas
   - `DB_NAME` = nome do banco (ex.: `dente_de_cobra`)
   - `JWT_SECRET` = um segredo novo e forte
   - `CORS_ORIGINS` = `https://xitios660-ctrl.github.io`
4. Deploy. Anote a URL pública, ex.: `https://dente-backend.onrender.com`.

> ⚠️ Confirme no seu `backend/server.py` que o CORS lê `CORS_ORIGINS` e inclui
> `https://xitios660-ctrl.github.io`. Sem isso o navegador bloqueia as chamadas.
> No free tier o backend "dorme" — a 1ª requisição demora alguns segundos.

### 2.3 Ligar o frontend ao backend
⚠️ **Importante:** em apps Create React App, `REACT_APP_BACKEND_URL` é "assado"
no momento do BUILD. Trocar depois não adianta — tem que rebuildar.

1. No `frontend/.env`, troque:
   ```
   REACT_APP_BACKEND_URL=https://dente-backend.onrender.com
   ```
   (a URL antiga `...preview.emergentagent.com` vai morrer — remova.)
2. Rebuild e republique:
   ```bash
   cd frontend
   npm run build
   npx gh-pages -d build
   ```
   (Opção B: refazer o `cp build/index.html build/404.html` antes de publicar.)

### 2.4 Teste o fluxo real
Adicionar ao carrinho → checkout → pedido salvo (nº DDC-XXXXXX) → painel `/admin`
(ou `/#/admin` na Opção A) → mudar status → rastreio do cliente atualiza.

---

## ✅ Checklist final
- [ ] Senha GitHub trocada + 2FA ativo
- [ ] Repo privado
- [ ] Senha admin e JWT_SECRET rotacionados; `backend/.env` fora do repo
- [ ] `index.html` e `Gh` removidos
- [ ] `homepage` no package.json
- [ ] HashRouter (ou basename + 404.html)
- [ ] Build publicado na branch `gh-pages`
- [ ] Pages apontando para `gh-pages` / (root)
- [ ] Atlas criado, backend no Render com CORS liberado
- [ ] `REACT_APP_BACKEND_URL` apontando pro Render + rebuild publicado
- [ ] Checkout + /admin testados no ar
