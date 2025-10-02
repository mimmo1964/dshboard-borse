# Market Dashboard – Istruzioni Deploy Streamlit Cloud

Questa dashboard mostra l'andamento delle borse mondiali utilizzando **Streamlit**, **yfinance** e (opzionalmente) **Alpha Vantage**.

## Come pubblicare su Streamlit Cloud

### 1. Carica su GitHub
- Crea un nuovo repository su GitHub (ad es. `dashboard-borse`).
- Carica i file: `app.py`, `requirements.txt`, `Dockerfile` (opzionale), `README.md`, `.env.example`.
- Non caricare **.env** con la chiave API.

### 2. Configura i “Secrets” su Streamlit Cloud
- Vai su https://share.streamlit.io → Sign in with GitHub.
- Collega il tuo repo.
- Clicca “New app” → scegli il branch e `app.py` → Deploy.

### 3. Aggiungi la chiave API come Secret
- Dopo il deploy, clicca “Manage app” → “Settings” → “Secrets”.
- Incolla:

```toml
ALPHA_API_KEY="LA_TUA_CHIAVE_ALPHA_VANTAGE"
```

- Salva. L’app si riavvierà automaticamente.

### 4. Testa l’app
- Apri il link generato (es. `https://tuo-nome.streamlit.app`).
- Nel menu laterale abilita “Usa Alpha Vantage (intraday)” per verificare.

### 5. Aggiorna l’app
- Fai modifiche in locale, poi `git push` su GitHub.
- Streamlit Cloud farà automaticamente il redeploy.

## Sicurezza
- Non includere mai chiavi API nel repository.
- Usa sempre la sezione “Secrets” del Cloud.
- Se cambi chiave API, aggiornala solo nei “Secrets” del Cloud.

