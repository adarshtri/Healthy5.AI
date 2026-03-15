# Running Healthy5.AI Locally (Event-Driven Architecture)

Because we have decoupled our architecture, running the backend now involves starting several independent processes. Instead of just running `uvicorn main:app`, we now have:
1. The **Redis Message Broker**
2. The **FastAPI Gateway** (receives webhooks)
3. The **RQ Workers** (Agent, Egress, Scheduler)

Here is how you start everything locally to test your code.

---

## Step 1: Start Redis

Redis is the durable queue that connects the Gateway to the Workers. The easiest way to run this locally on a Mac is via Docker.

If you don't have Redis installed natively (`brew install redis` -> `redis-server`), run this Docker command in any terminal:
```bash
docker run -d -p 6379:6379 --name healthy5-redis redis:alpine
```
*(This starts Redis on the default port `6379` which our `src.events.broker` expects).*

---

## Step 2: Start the Ingress Gateway (FastAPI)

This is the front-door that Telegram will hit.

1. Open a new terminal window.
2. Activate your virtual environment:
   ```bash
   cd backend
   source venv/bin/activate
   ```
3. Start the FastAPI app from the `src.gateway` module:
   ```bash
   uvicorn src.gateway.main:app --reload
   ```

> **Testing Webhooks:** If you are testing Telegram webhooks locally, you will still need to run `ngrok http 8000` in a separate window and use your `scripts/set_webhook.py` to point Telegram to `https://<ngrok-url>.ngrok-free.app/webhook/telegram/<YOUR_BOT_TOKEN>`.

---

## Step 3: Start the Workers

Workers pull jobs from the queues. Ideally, you run each worker in its own terminal window so you can easily trace logs (e.g., "Agent crashed" vs "Message failed to send").

**In a new terminal window (Agent Worker):**
```bash
cd backend
source venv/bin/activate
# This tells RQ to listen to the 'incoming_messages' queue
rq worker incoming_messages
```

**In a new terminal window (Egress Worker):**
```bash
cd backend
source venv/bin/activate
# This tells RQ to listen to the 'outgoing_messages' queue
rq worker outgoing_messages
```

*(Optional) In a new terminal window (Scheduler Worker):*
If you want to test reminders, you can run the scheduler. Note: We refactored `scheduler.py` but haven't written the exact CLI entrypoint yet.

---

## How to Test the Flow

1. Make sure Redis, the Gateway, and both Workers are running.
2. Send a message to your Telegram Bot.
3. **Watch the Terminals:**
   * **Gateway Terminal:** You should see `POST /webhook/telegram/... 200 OK` (It accepted the message and pushed to the queue).
   * **Agent Worker Terminal:** You should see logs from LangGraph generating the response, followed by `[Agent Worker] Queued response for Delivery...`.
   * **Egress Worker Terminal:** You should see `[Egress Worker] Sending message...` and then `Successfully sent...`.
4. You should receive the message in Telegram!
