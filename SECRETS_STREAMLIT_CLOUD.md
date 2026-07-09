# Configuração no Streamlit Community Cloud

## 1. Fazer deploy

1. Acesse https://share.streamlit.io
2. Faça login com GitHub
3. Clique em **"New app"**
4. Selecione o repositório `ronneyramos/prumo`
5. **Main file path:** `streamlit/main.py`
6. **App URL:** `prumoerp.streamlit.app` (já registrado)
7. Clique em **"Deploy"**

## 2. Configurar Secrets

No dashboard do app, vá em **⚙️ Settings → Secrets** e cole as variáveis abaixo
com os valores do arquivo `.env` da sua máquina:

```toml
SUPABASE_URL = "https://SEU_PROJETO.supabase.co"
SUPABASE_ANON_KEY = "sua_anon_key"
SUPABASE_SERVICE_KEY = "sua_service_key"
ALERT_EMAIL_FROM = "seu_email@gmail.com"
ALERT_EMAIL_PASSWORD = "sua_senha_app"
ALERT_EMAIL_TO = "destinatario@gmail.com"
```

> ⚠️ Copie os valores reais do arquivo `streamlit/.env` da sua máquina.

## 3. Acessar

- **URL:** https://prumoerp.streamlit.app/
- **Atualizações:** Basta dar `git push` que o Streamlit Cloud faz redeploy automático
