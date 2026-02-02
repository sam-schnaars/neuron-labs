# Running Grokie with Docker (e.g. on Linux)

Use this to run the full Grokie stack (LiveKit + Python agent + web app) on a Linux machine (or any host with Docker) without installing Node, Python, or LiveKit locally.

## What you need on the Linux machine

- **Docker** and **Docker Compose** (v2+)
- Your **xAI API key** (for the voice agent)

## 1. Copy the project to Linux

Copy the whole `Grokie` folder (or the repo) to your Linux computer. You can use `rsync`, `scp`, or git:

```bash
# Example: from your Mac, sync Grokie to Linux
rsync -avz --exclude node_modules --exclude venv --exclude conversation_memory Grokie/ user@linux-host:~/Grokie/
```

Or clone/pull the repo on Linux if you use git.

## 2. Create `.env` on the Linux machine

In the `Grokie` directory, create a `.env` file with your keys (do **not** commit this file):

```bash
cd ~/Grokie
cp .env.example .env
nano .env   # or vim
```

Set at least:

- **`XAI_API_KEY`** – your xAI (Grok) API key (required for the agent).
- Optionally override LiveKit credentials (defaults are fine for local use):
  - `LIVEKIT_API_KEY=devkey`
  - `LIVEKIT_API_SECRET=secret`

Example `.env`:

```env
XAI_API_KEY=your-xai-api-key-here
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

## 3. Build and run with Docker Compose

From the `Grokie` directory:

```bash
cd ~/Grokie
docker compose up --build
```

First run will build the agent and web images and pull LiveKit; later runs are quick.

When everything is up you should see the token server and agent running. Then:

- Open **http://localhost:8080** in a browser on that machine (or from another machine if you use the host’s IP and firewall allows 8080).
- Use the UI to connect, allow microphone, and talk to the agent.

To run in the background:

```bash
docker compose up --build -d
```

To stop:

```bash
docker compose down
```

## 4. Ports

| Port | Service        | Use                          |
|------|----------------|------------------------------|
| 7880 | LiveKit        | WebSocket (browser connects) |
| 8080 | Web + token API| App and token endpoint       |

If you need to change the web port (e.g. 80), set `PORT=80` for the `web` service and map it in `docker-compose.yml` (e.g. `"80:80"`).

## 5. Data (conversation memory)

Conversation memory and event data are stored in Docker volumes:

- `grokie_memory` – conversation history, lesson plans, pitches
- `grokie_events` – attendee/event data

They persist across `docker compose down`. To remove them:

```bash
docker compose down -v
```

## 6. Troubleshooting

- **Agent won’t start** – Check that `XAI_API_KEY` is set in `.env` and that the `agent` container can reach `livekit` (e.g. `docker compose logs agent`).
- **“Failed to generate token”** – Ensure `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` in `.env` match the LiveKit defaults (`devkey` / `secret`) when using `--dev`, or your custom LiveKit config.
- **Can’t open from another machine** – Use the Linux host’s IP (e.g. `http://192.168.1.10:8080`). The frontend uses `ws://localhost:7880` for LiveKit; from another machine you’d need to either proxy WebSockets or build the frontend with a different LiveKit URL (e.g. `VITE_LIVEKIT_URL=ws://HOST_IP:7880` when building).

## Files added for Docker

- **`.env.example`** – Template for `.env` (copy to `.env` and fill in keys).
- **`Dockerfile.agent`** – Python voice agent image.
- **`Dockerfile.web`** – Node app: build frontend + token server, serve on 8080.
- **`docker-compose.yml`** – Defines `livekit`, `agent`, and `web` services and volumes.
- **`DOCKER.md`** – This file.

The web server serves the built frontend from the same port (8080) when `dist/` exists (e.g. in Docker); locally you can still use `./run-all.sh` with the Vite dev server on 3000.
