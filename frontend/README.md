# Workways FAQ Scorer — Frontend (Streamlit)

## Lancer en local

1) Installer
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) Configurer l'URL backend
Option A (env):
```bash
export BACKEND_BASE_URL="http://localhost:8000"
```

Option B (.env):
- copier `.env.example` → `.env`
- éditer `BACKEND_BASE_URL`

Option C (Streamlit secrets):
- copier `frontend/.streamlit/secrets.toml.example` → `frontend/.streamlit/secrets.toml`

3) Lancer
```bash
streamlit run app.py
```