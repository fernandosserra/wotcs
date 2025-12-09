# 📘 **WOTCS — World of Tanks Clan System**

WOTCS é uma aplicação web desenvolvida para administração de clãs no *World of Tanks*.  
O sistema centraliza informações de jogadores, tanques, estatísticas analíticas e fornece um painel seguro para comandantes e membros do clã.

A aplicação utiliza a API oficial da Wargaming para sincronização de dados, mantendo um cache otimizado e realizando atualizações periódicas de forma eficiente.

---

## 🚀 **Principais Recursos**

### ✔ Painel Analítico
- Filtragem por jogador, tier, nação e tipo de tanque  
- Paginação configurável  
- Estatísticas consolidadas da seleção:
  - Média de batalhas  
  - Percentual de vitória  
  - Total de marcas de maestria  

### ✔ Gestão de Usuários
- Registro de membros do clã com validação via API da WG  
- Login autenticado via cookies (sessão simples)  
- Controle de acesso por *role* (member / commander)

### ✔ Sincronização Automática com Wargaming
- Coleta incremental de tanques via `/account/tanks/`  
- Enriquecimento com metadata via `/encyclopedia/vehicles/`  
- Cache em disco para reduzir chamadas e aumentar performance  
- *Scheduler* com APScheduler (sync periódico)

### ✔ Banco de Dados
- Persistência via PostgreSQL  
- ORM baseado em **SQLModel** (SQLAlchemy + Pydantic)  
- Atualização segura de dados, limpeza por jogador e inserção otimizada

---

## 🏗 **Arquitetura**

```
app/
│
├── api/
│   ├── auth.py          → registro/login/logout
│   ├── admin.py         → rotas administrativas
│
├── models/
│   ├── models.py        → User, Player, GarageTank
│
├── utils/
│   ├── tank_cache.py    → leitura/gravação do cache de veículos
│
├── templates/           → HTML (Jinja2)
├── static/              → CSS, JS
│
├── db.py                → engine + init_db
└── main.py              → aplicação FastAPI
```

---

## 📦 **Requisitos**

- Python 3.10+
- PostgreSQL 13+
- pip / venv
- (Opcional) **cloudflared** para expor a aplicação externamente

---

## ⚙️ **Configuração**

### 1. Criar ambiente virtual

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

---

### 2. Criar o arquivo `.env` (não versionar)

```env
WOT_APP_ID=SEU_APP_ID
CLAN_ID=ID_DO_SEU_CLA
WOT_REALM=https://api.worldoftanks.com

DATABASE_URL=postgresql+psycopg2://user:senha@localhost:5432/wotcs
SECRET_KEY=troque-por-uma-chave-segura
```

---

### 3. Inicializar o banco

A aplicação cria as tabelas automaticamente no startup:

```bash
uvicorn app.main:app --reload
```

---

## 🔄 **Sincronização Automática**

O sistema mantém um processo de sincronização que:

1. Busca membros do clã  
2. Busca tanques por jogador  
3. Completa o metadata pelo cache ou API  
4. Regrava a tabela `garagetank`  
5. Salva o cache incremental  

O scheduler executa a cada **20 minutos**.

Você também pode acionar manualmente:

```
GET /sync/check
```

---

## 🧪 **Scripts Úteis (pasta scripts/)**

| Script | Função |
|--------|--------|
| `inspect_db.py` | Diagnóstico do banco e modelos |
| `rehydrate_from_cache.py` | Reconstroi a tabela `garagetank` usando o cache |
| `...` | Outros scripts auxiliares |

---

## 🔐 **Segurança**

### Arquivos que **NÃO DEVEM ir para o Git**:
- `.env`
- `data/tank_cache.json`
- `data/members_cache.json`
- logs (`*.log`)
- virtualenv (`env/` ou `.venv/`)
- banco local (`*.sqlite3`)

O projeto já inclui um `.gitignore` adequado.

---

## 🌐 **Hospedagem / Exposição**

Você pode rodar a aplicação em:
- **Notebook Ubuntu** + Cloudflare Tunnel  
- VPS (DigitalOcean, Hetzner, AWS EC2)  
- Docker / Docker Compose  
- Railway / Render (caso queira gratuito/limitado)  

Se quiser, posso gerar:

✔ `docker-compose.yml`  
✔ Arquivo `systemd`  
✔ Tutorial Cloudflare Tunnel  

---

## 📝 **Como Rodar em Produção (resumo)**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Com workers:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000
```

---

## 🤝 **Contribuição**

Pull requests são bem-vindos.  
A criação de issues para bugs, melhorias ou dúvidas é incentivada.

---

## 📄 **Licença**

Este projeto é privado e não possui licença pública atribuída.  
Todos os direitos reservados ao proprietário do repositório.