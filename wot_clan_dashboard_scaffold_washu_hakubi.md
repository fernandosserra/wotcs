# WOT Clan Dashboard — Scaffold Inicial (por Dra. Washu Hakubi)

Nada menos do que o esperado da maior cientista do universo: aqui está o scaffold inicial do seu projeto **WOT Clan Dashboard**, pronto para rodar localmente.

> **Observação:** este documento contém os arquivos iniciais (conteúdo fonte). Abra-o e copie/cole os arquivos para seu repositório local, ou use-o como referência.

---

## Árvore de arquivos criada

```
WOTCS/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ api/__init__.py
│  ├─ core/__init__.py
│  ├─ jobs/__init__.py
│  ├─ models/__init__.py
│  ├─ services/__init__.py
│  ├─ utils/__init__.py
│  ├─ templates/
│  └─ static/
│     ├─ css/
│     ├─ js/
│     └─ img/
├─ config/
│  └─ settings.example.env
├─ data/
├─ docs/
├─ env/
├─ logs/
├─ scripts/
│  ├─ deploy/
│  └─ maintenance/
├─ tests/
├─ requirements.txt
├─ README.md
└─ .gitignore
```

---

## Arquivos principais (conteúdo)

> **Importante:** não repita manualmente este conteúdo sem ajustar as variáveis de ambiente (`.env`) e a `WOT_APP_ID` antes de rodar.

### `app/main.py`
```python
# Entrada mínima para desenvolvimento local - FastAPI
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import SQLModel, create_engine, Session, select
from passlib.context import CryptContext
import os
import httpx
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Config via env
WOT_APP_ID = os.getenv("WOT_APP_ID", "")
CLAN_ID = os.getenv("CLAN_ID", "")
WOT_REALM = os.getenv("WOT_REALM", "https://api.worldoftanks.eu")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/db.sqlite3")

pwdctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
app = FastAPI(title="WOT Clan Dashboard")

# Model placeholders (implemente melhor conforme evolui)
from sqlmodel import Field
from typing import Optional

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    password_hash: str
    role: str = "member"

class Player(SQLModel, table=True):
    account_id: int = Field(primary_key=True)
    nickname: str

class GarageTank(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int
    tank_id: int
    tank_name: str
    tier: int


def init_db():
    SQLModel.metadata.create_all(engine)

# Auth helpers - para POC local (melhore para produção)
def verify_password(plain, hashed):
    return pwdctx.verify(plain, hashed)

def hash_password(pw):
    return pwdctx.hash(pw)

# Simple cookie-based demo auth
from fastapi import Form
from fastapi.security import OAuth2PasswordRequestForm

@app.post('/login')
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == form_data.username)).first()
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=400, detail='Usuário/senha inválidos')
        resp = RedirectResponse(url='/dashboard', status_code=302)
        resp.set_cookie(key='user', value=user.username, httponly=True, secure=False)
        return resp


def get_current_user(request: Request):
    username = request.cookies.get('user')
    if not username:
        raise HTTPException(status_code=401, detail='Não autenticado')
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if not user:
            raise HTTPException(status_code=401, detail='Usuário não existe')
        return user


@app.get('/', response_class=HTMLResponse)
async def index():
    return HTMLResponse('<h3>WOT Clan Dashboard — Em desenvolvimento</h3>')


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request, tier: Optional[int] = None, current_user: User = Depends(get_current_user)):
    with Session(engine) as s:
        q = select(GarageTank, Player).join(Player, GarageTank.account_id == Player.account_id)
        if tier:
            q = q.where(GarageTank.tier == tier)
        rows = s.exec(q).all()
    html = f"<h1>Dashboard do Clã</h1><p>Usuário: {current_user.username} ({current_user.role})</p>"
    for gt, ply in rows:
        html += f"<div>{ply.nickname} — {gt.tank_name} (Tier {gt.tier})</div>"
    return HTMLResponse(html)


# Sync job (POC simplificado)
async def fetch_and_sync():
    if not WOT_APP_ID or not CLAN_ID:
        return
    async with httpx.AsyncClient(timeout=30) as client:
        members_url = f"{WOT_REALM}/wot/clans/info/?application_id={WOT_APP_ID}&clan_id={CLAN_ID}&extra=members"
        try:
            r = await client.get(members_url)
            r.raise_for_status()
            data = r.json()
            members = data.get('data', {}).get(str(CLAN_ID), {}).get('members', [])
        except Exception:
            return

        with Session(engine) as s:
            for m in members:
                acc_id = m['account_id']
                nickname = m.get('nickname', f'player_{acc_id}')
                p = s.get(Player, acc_id)
                if not p:
                    p = Player(account_id=acc_id, nickname=nickname)
                else:
                    p.nickname = nickname
                s.add(p)
            s.commit()

            for m in members:
                acc_id = m['account_id']
                tanks_url = f"{WOT_REALM}/wot/account/tanks/?application_id={WOT_APP_ID}&account_id={acc_id}"
                rr = await client.get(tanks_url)
                if rr.status_code != 200:
                    continue
                j = rr.json()
                items = j.get('data', {}).get(str(acc_id), [])
                # delete old tanks for this account
                s.exec(select(GarageTank).where(GarageTank.account_id == acc_id)).all()
                for t in items:
                    tank_id = t.get('tank_id')
                    # get tank meta
                    tm = await client.get(f"{WOT_REALM}/wot/encyclopedia/tanks/?application_id={WOT_APP_ID}&tank_id={tank_id}")
                    if tm.status_code != 200:
                        continue
                    tmj = tm.json()
                    meta = tmj.get('data', {}).get(str(tank_id), {})
                    tier = meta.get('tier', 0)
                    if tier not in (6, 8, 10):
                        continue
                    tank_name = meta.get('name', f'Tank {tank_id}')
                    gt = GarageTank(account_id=acc_id, tank_id=tank_id, tank_name=tank_name, tier=tier)
                    s.add(gt)
                s.commit()


@app.on_event('startup')
async def startup_event():
    init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(fetch_and_sync, 'interval', minutes=15)
    scheduler.start()

# To run locally: uvicorn app.main:app --reload --port 8000
```

### `config/settings.example.env`
```
# Example environment variables
WOT_APP_ID=
CLAN_ID=
WOT_REALM=https://api.worldoftanks.eu
DATABASE_URL=sqlite:///./data/db.sqlite3
SECRET_KEY=change-me-to-a-strong-secret
```

### `requirements.txt`
```
fastapi
uvicorn[standard]
sqlmodel
httpx
apscheduler
passlib[bcrypt]
python-dotenv
```

### `.gitignore`
```
__pycache__/
*.pyc
.env
data/db.sqlite3
env/
.vscode/
.idea/
logs/
```

### `README.md` (resumo rápido)
```md
# WOT Clan Dashboard — POC local

## Setup rápido (PowerShell)

```powershell
python -m venv env
env\Scripts\Activate.ps1
pip install -r requirements.txt
cp config\settings.example.env .env   # ajuste variáveis
uvicorn app.main:app --reload --port 8000
```

Acesse: http://localhost:8000

> Nota: este é um scaffold POC. Em produção, habilite HTTPS, proteja secrets e use um DB gerenciado.
```

---

## Arquivo de imagem carregado (opcional)

Há um arquivo de imagem disponível no ambiente que podemos usar como logo/placeholder do projeto:

`/mnt/data/44508-Washu-Hakubi-Plush-from-Tenchi-Muyo.jpg`

Se quiser, eu incluo esse arquivo na pasta `app/static/img` do scaffold e adapto o `README` para usá-lo.

---

## Próximos passos que eu já posso executar para você (escolha o que preferir):

1. Gerar `Dockerfile` + `docker-compose.yml` para rodar on-premises (recomendado para migração futura).
2. Criar exemplo `app/api/auth.py` com routes de login/registro e hashing seguro (bcrypt) e proteção de rota por role.
3. Criar script PowerShell para criar e ativar virtualenv, instalar dependências e rodar localmente.
4. Adicionar cache simples para encyclopedia/tanks (arquivo JSON em `data/`) e usar para evitar chamadas repetidas.

Diga qual (ou quais) eu já gero e eu prossigo com a valentia científica da maior mente do universo.

---

*Documento gerado pela Dra. Washu Hakubi — mente de 12 dimensões.*



---

## Adições: `dashboard.html` e ajustes em `app/api/auth.py` + melhorias nos templates de login/register

Abaixo estão os arquivos prontos para você copiar para o repositório local:

### `app/templates/dashboard.html`
```html
{% extends "base.html" %}
{% block content %}

<h2 style="text-align:center; color:#f06292;">Dashboard do Clã</h2>

<p style="text-align:center; margin-bottom:12px; color:#ddd;">Bem-vindo, {{ user.username }} — Lema: <strong>"Danonão Grosso"</strong></p>

<div style="text-align:center; margin-bottom:18px;">
    <img src="/static/img/logo.jpg" alt="logo" style="max-height:80px; border-radius:6px; box-shadow:0 0 12px rgba(240,98,146,0.25);">
</div>

<table style="width:100%; border-collapse: collapse;">
    <thead>
        <tr style="background:#1b1f1b; color:#f06292; text-transform:uppercase;">
            <th style="padding:10px; border-bottom:1px solid #333; text-align:left;">Jogador</th>
            <th style="padding:10px; border-bottom:1px solid #333;">Tank</th>
            <th style="padding:10px; border-bottom:1px solid #333;">Tier</th>
        </tr>
    </thead>
    <tbody>
    {% for gt, ply in rows %}
        <tr style="border-bottom:1px solid #2a2f2a;">
            <td style="padding:10px;">{{ ply.nickname }}</td>
            <td style="padding:10px; text-align:center;">{{ gt.tank_name }}</td>
            <td style="padding:10px; text-align:center;">{{ gt.tier }}</td>
        </tr>
    {% else %}
        <tr>
            <td colspan="3" style="padding:12px; text-align:center; color:#bbb;">Nenhum tank encontrado para o filtro selecionado.</td>
        </tr>
    {% endfor %}
    </tbody>
</table>

<p style="margin-top:18px; text-align:center;">
    <a href="/auth/register">Registrar novo membro</a> • <a href="/auth/login">Sair / Trocar usuário</a>
</p>

{% endblock %}
```

> Observação: coloque uma imagem de logo no caminho `app/static/img/logo.jpg`. Você pode usar a imagem que já existe no ambiente em `/mnt/data/44508-Washu-Hakubi-Plush-from-Tenchi-Muyo.jpg` — copie para `app/static/img/logo.jpg` no projeto. O caminho local da imagem disponível é: `/mnt/data/44508-Washu-Hakubi-Plush-from-Tenchi-Muyo.jpg`.

---

### `app/api/auth.py` (ATUALIZADO — POSTs redirecionam para páginas de template e incluem mensagens via query string)
```python
# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from passlib.context import CryptContext
from typing import Optional

from app.db import engine
from app.models import User

pwdctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

# Helpers
def hash_password(pw: str) -> str:
    return pwdctx.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwdctx.verify(plain, hashed)

@router.post('/register')
def register(username: str = Form(...), password: str = Form(...), role: Optional[str] = Form('member')):
    with Session(engine) as s:
        existing = s.exec(select(User).where(User.username == username)).first()
        if existing:
            # redireciona de volta para a página de registro com mensagem de erro
            return RedirectResponse(url=f"/auth/register?msg=exists", status_code=303)
        u = User(username=username, password_hash=hash_password(password), role=role)
        s.add(u)
        s.commit()
    # ao registrar com sucesso, redireciona para a página de login com mensagem
    return RedirectResponse(url=f"/auth/login?msg=registered", status_code=303)

@router.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if not user or not verify_password(password, user.password_hash):
            return RedirectResponse(url=f"/auth/login?msg=invalid", status_code=303)
        resp = RedirectResponse(url='/dashboard', status_code=303)
        resp.set_cookie(key='user', value=user.username, httponly=True, secure=False)
        return resp

@router.post('/logout')
def logout():
    resp = RedirectResponse(url='/', status_code=303)
    resp.delete_cookie('user')
    return resp
```

---

### Pequenas melhorias nos templates de `login.html` e `register.html` (mostrar mensagens via query string)

Atualize os dois templates para exibir mensagens curtas quando o parâmetro `msg` estiver presente nas query params.

#### `app/templates/login.html` (trecho para substituir no topo do bloco content)
```html
{% set m = request.query_params.get('msg') %}
{% if m == 'registered' %}
  <div style="background:#2b2; padding:8px; border-radius:4px; margin-bottom:12px; color:#012; text-align:center;">Conta criada com sucesso. Faça login.</div>
{% elif m == 'invalid' %}
  <div style="background:#f88; padding:8px; border-radius:4px; margin-bottom:12px; color:#400; text-align:center;">Usuário ou senha inválidos.</div>
{% endif %}
```

#### `app/templates/register.html` (trecho para substituir no topo do bloco content)
```html
{% set m = request.query_params.get('msg') %}
{% if m == 'exists' %}
  <div style="background:#f88; padding:8px; border-radius:4px; margin-bottom:12px; color:#400; text-align:center;">Usuário já existe. Escolha outro.</div>
{% endif %}
```

---

Coloque esses arquivos no projeto e reinicie o servidor (uvicorn). As rotas `/auth/register` e `/auth/login` agora exibem mensagens amigáveis após operações de POST, e o dashboard tem template simples com tabela.

Se quiser, eu copio o logo local automaticamente para `app/static/img/logo.jpg` no scaffold (se tiver acesso) — ou te dou o comando PowerShell para copiar ele a partir do path `/mnt/data/44508-Washu-Hakubi-Plush-from-Tenchi-Muyo.jpg`.

Quer que eu gere o comando PowerShell para copiar a imagem e reiniciar o servidor por você? Caso sim, digo o comando exato.

