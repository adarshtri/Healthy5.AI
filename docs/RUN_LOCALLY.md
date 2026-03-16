# Running Healthy5.AI Locally

## Prerequisites

- Python 3.12+
- Node.js 18+
- Redis running on `localhost:6379` (via `docker run -d -p 6379:6379 redis:alpine` or `brew services start redis`)
- MongoDB running locally or a MongoDB Atlas connection string
- ngrok or Cloudflare Tunnel (for Telegram webhook testing)

## 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create an admin user (first time only):
```bash
python scripts/create_admin.py <username> <password>
```

Start all services (Gateway + Workers):
```bash
cd scripts
./start_dev.sh
```

The API will be available at `http://localhost:8000`.

## 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` and log in with your admin credentials.

## 3. Configure System Settings

Go to **Admin Dashboard** → **System Settings** → **Edit Settings** and fill in:
- Groq API Key (or switch to Ollama for local models)
- Redis URL
- JWT Secret Key

Click **Save Settings**.

## 4. Telegram Webhooks (optional)

Expose your backend publicly:
```bash
ngrok http 8000
```

Paste the HTTPS URL into **Admin Dashboard → Telegram Webhook URL**, then click **Sync Webhooks Now**.

## Stopping Services

Press `Ctrl+C` in the `start_dev.sh` terminal. If workers linger:
```bash
pkill -f "rq worker"
```
