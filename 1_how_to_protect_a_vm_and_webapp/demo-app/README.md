## How to run the Demo Application

**1. With virtual environment (recommended)**

```bash
conda create -n demo-app python=3.12
conda activate demo-app
pip install -r backend/requirements.txt

cd backend
export DATABASE_URL="sqlite:///demo.db"
export FLASK_APP=app:app
flask run --host=0.0.0.0 --port=8000
```

**2. With docker compose**

```bash
docker compose up --build -d
```

**3. Access the application**
Go to `http://127.0.0.1:8000` in your web browser to access the demo application.
