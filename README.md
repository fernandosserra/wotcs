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