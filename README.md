# Private Messenger Backend

A production-ready, secure, and modular backend built with **Python 3.12+**, **FastAPI**, **PostgreSQL**, **WebSockets**, **WebRTC Signaling**, and **SQLAlchemy 2.x**.

Engineered specifically for personal use, trusted friends, and small-team communication with zero ads, zero tracking, and zero public social media noise.

---

## Table of Contents

1. [What This Backend Does](#1-what-this-backend-does)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [Local Installation](#3-local-installation)
4. [PostgreSQL Database Setup](#4-postgresql-database-setup)
5. [Environment Variables Guide](#5-environment-variables-guide)
6. [Database Migrations (Alembic)](#6-database-migrations-alembic)
7. [Running Locally](#7-running-locally)
8. [Interactive API Documentation](#8-interactive-api-documentation)
9. [WebSocket Real-Time Architecture](#9-websocket-real-time-architecture)
10. [WebRTC Audio & Video Calling Flow](#10-webrtc-audio--video-calling-flow)
11. [File & Media Storage](#11-file--media-storage)
12. [Firebase Cloud Messaging (Push Notifications)](#12-firebase-cloud-messaging-push-notifications)
13. [Render Production Deployment (Step-by-Step)](#13-render-production-deployment-step-by-step)
14. [Render Cold Start & Server Status](#14-render-cold-start--server-status)
15. [Exact URLs the Mobile App Needs](#15-exact-urls-the-mobile-app-needs)
16. [Connecting the Mobile App](#16-connecting-the-mobile-app)
17. [Troubleshooting Guide](#17-troubleshooting-guide)
18. [Mobile App Connection Values (Summary Table)](#18-mobile-app-connection-values)

---

## 1. What This Backend Does

- **Simple & Safe Authentication**: Sign up and log in using only a `username` and `password`. No phone numbers, no email addresses, no SMS verification. Passwords securely hashed with **Argon2** / **bcrypt**.
- **1-to-1 Private Messaging**: Idempotent conversation opening, real-time message exchange, unread counts, editing, and soft-deletes.
- **Group Chats**: Create group chats, add and remove participants, leave groups, and rename group titles.
- **Username Search**: Find friends by searching usernames without exposing sensitive metadata or password hashes.
- **Rich Media & File Uploads**: Upload images, voice messages, videos, and documents with file size and MIME-type validation. Pluggable storage abstraction supporting local disk and **S3 / Cloudflare R2 / MinIO**.
- **Audio & Video Call Signaling**: WebRTC peer-to-peer signaling via WebSockets (`call:offer`, `call:answer`, `call:ice-candidate`, `call:reject`, `call:end`, `call:busy`). The server never processes or records raw media streams.
- **Real-Time Presence & Typing Indicators**: Instant online/offline statuses and in-memory typing events without database polling overhead.
- **Message Status Delivery & Read Receipts**: Delivery confirmations and read receipts synced across all active devices.
- **Push Notifications**: Pluggable Firebase Cloud Messaging (FCM) abstraction for wake-up notifications on incoming messages and calls.

---

## 2. Prerequisites & System Requirements

- **Python**: Version 3.12 or higher (Python 3.10+ also supported)
- **PostgreSQL**: Version 14, 15, or 16
- **Pip & Virtualenv**: `python3 -m venv`
- **Docker** (Optional, for containerized deployments)

---

## 3. Local Installation

```bash
# 1. Clone repository and navigate to backend directory
cd backend

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Activate the virtual environment
# On Linux / macOS:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# 4. Upgrade pip and install all required dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. PostgreSQL Database Setup

### Option A: Local PostgreSQL
Make sure PostgreSQL is running on your machine, then create a database:

```bash
# Open PostgreSQL shell
psql -U postgres

# In psql prompt:
CREATE DATABASE messenger;
CREATE USER messenger_user WITH ENCRYPTED PASSWORD 'messenger_password';
GRANT ALL PRIVILEGES ON DATABASE messenger TO messenger_user;
\q
```

### Option B: Docker PostgreSQL (Fastest for Local Dev)
```bash
docker run -d \
  --name messenger-postgres \
  -e POSTGRES_DB=messenger \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16-alpine
```

---

## 5. Environment Variables Guide

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Server
ENVIRONMENT=development
PORT=8000
HOST=0.0.0.0
SERVER_PUBLIC_URL=http://localhost:8000

# Database (AsyncPG URL)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/messenger

# Security & JWT Token
# Generate a secret: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=super_secret_production_key_minimum_32_characters_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# WebRTC STUN/TURN (Publicly accessible)
STUN_SERVER=stun:stun.l.google.com:19302
STUN_SERVER_SECONDARY=stun:stun1.l.google.com:19302
TURN_SERVER=
TURN_USERNAME=
TURN_PASSWORD=

# Media Storage
STORAGE_PROVIDER=local
LOCAL_UPLOAD_DIR=uploads
MAX_FILE_SIZE_BYTES=52428800

# Firebase Cloud Messaging (Optional)
FIREBASE_PROJECT_ID=
FIREBASE_CLIENT_EMAIL=
FIREBASE_PRIVATE_KEY=
```

---

## 6. Database Migrations (Alembic)

Apply all database migrations up to the latest revision:

```bash
alembic upgrade head
```

To create a new migration after modifying models in `app/models/`:

```bash
alembic revision --autogenerate -m "describe_changes"
alembic upgrade head
```

---

## 7. Running Locally

Start the Uvicorn development server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be accessible at:
- **API Base**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc UI**: `http://localhost:8000/redoc`
- **WebSocket**: `ws://localhost:8000/ws?token=<JWT_TOKEN>`
- **Health Check**: `http://localhost:8000/health`

---

## 8. Interactive API Documentation

FastAPI automatically generates interactive Swagger documentation at `/docs`.

### Key Endpoints Summary:

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Health check probe | No |
| `POST` | `/api/auth/register` | Register with username & password | No |
| `POST` | `/api/auth/login` | Log in and receive JWT token | No |
| `GET` | `/api/auth/me` | Fetch currently logged in user profile | Yes |
| `GET` | `/api/users/search?username=` | Case-insensitive username search | Yes |
| `GET` | `/api/users/{user_id}` | Fetch public user profile | Yes |
| `PATCH` | `/api/users/me/avatar` | Update avatar URL | Yes |
| `POST` | `/api/chats` | Create direct (1-to-1) or group chat | Yes |
| `GET` | `/api/chats` | List user conversations with unread counts | Yes |
| `GET` | `/api/chats/{chat_id}` | Get chat details and participant roster | Yes |
| `PATCH` | `/api/chats/{chat_id}` | Update group title/avatar (Owner only) | Yes |
| `POST` | `/api/chats/{chat_id}/members` | Add members to group chat | Yes |
| `DELETE` | `/api/chats/{chat_id}/members/{id}`| Remove member from group | Yes |
| `POST` | `/api/chats/{chat_id}/leave` | Leave group chat | Yes |
| `POST` | `/api/chats/{chat_id}/messages` | Send text, voice, media, or file | Yes |
| `GET` | `/api/chats/{chat_id}/messages` | Paginated message history | Yes |
| `PATCH` | `/api/messages/{message_id}` | Edit message text | Yes |
| `DELETE` | `/api/messages/{message_id}` | Soft-delete message | Yes |
| `POST` | `/api/messages/{message_id}/delivered`| Mark message delivered | Yes |
| `POST` | `/api/chats/{chat_id}/read` | Mark conversation messages as read | Yes |
| `POST` | `/api/files/upload` | Upload media / attachment file | Yes |
| `GET` | `/api/calls/config` | Retrieve WebRTC STUN/TURN config | Yes |
| `POST` | `/api/calls/initiate` | Log initiated call & notify receiver | Yes |
| `POST` | `/api/calls/{call_id}/end` | End call session | Yes |
| `GET` | `/api/calls/history` | Call logs for user | Yes |
| `POST` | `/api/devices/register` | Register FCM push device token | Yes |
| `DELETE` | `/api/devices/{token}` | Unregister device token on logout | Yes |

---

## 9. WebSocket Real-Time Architecture

Connect to the WebSocket endpoint:

```
ws://<HOST>/ws?token=<JWT_ACCESS_TOKEN>
```

### Real-Time Events Received by Client:

```json
// New Message Received
{
  "event": "message:new",
  "data": {
    "id": 42,
    "chat_id": 1,
    "sender_id": 2,
    "message_type": "text",
    "text": "Hey there!",
    "created_at": "2026-09-22T09:00:00Z"
  }
}

// User Started / Stopped Typing
{
  "event": "typing:start",
  "data": {
    "chat_id": 1,
    "user_id": 2,
    "username": "alex"
  }
}

// Contact Came Online
{
  "event": "user:online",
  "data": {
    "user_id": 2,
    "username": "alex"
  }
}

// Contact Went Offline
{
  "event": "user:offline",
  "data": {
    "user_id": 2,
    "username": "alex",
    "last_seen": "2026-09-22T09:15:00Z"
  }
}
```

### Sending Events from Client to Server:

```json
// Send Typing Indicator
{
  "event": "typing:start",
  "data": { "chat_id": 1 }
}

// Stop Typing Indicator
{
  "event": "typing:stop",
  "data": { "chat_id": 1 }
}

// Ping / Keep-Alive Heartbeat
{
  "event": "ping"
}
```

---

## 10. WebRTC Audio & Video Calling Flow

The backend functions as a pure **signaling relay**. Media streams (RTP/SRTP audio & video) flow directly peer-to-peer between client devices or via TURN relay. The backend never records or intercepts media streams.

```
User A (Caller)                     Backend WebSocket                   User B (Callee)
      │                                     │                                  │
      ├── POST /api/calls/initiate ────────>│                                  │
      │   (Status: initiated)               │                                  │
      │                                     │                                  │
      ├── WebSocket: call:offer ───────────>│                                  │
      │   { target_user_id, offer, type }   │── WebSocket: call:offer ────────>│
      │                                     │   (Ringing popup / Push)         │
      │                                     │                                  │
      │                                     │<── WebSocket: call:answer ───────┤
      │<── WebSocket: call:answer ──────────┤   { target_user_id, answer }     │
      │                                     │                                  │
      │<── WebSocket: call:ice-candidate ──>│<── WebSocket: call:ice-candidate─┤
      │                                     │                                  │
      │══════════════ Direct WebRTC P2P Audio/Video Connection ════════════════│
      │                                                                        │
      ├── WebSocket: call:end ─────────────>│── WebSocket: call:end ──────────>│
      │                                     │                                  │
      └── POST /api/calls/{id}/end ────────>│                                  │
```

---

## 11. File & Media Storage

The application provides a pluggable storage interface in `app/services/storage.py`.

### Local Disk Storage (Default for development)
Files are stored locally in the `uploads/` folder and served through FastAPI's static file handler at `/uploads/...`.

### Cloud Object Storage (S3 / Cloudflare R2 / MinIO)
For production deployments on Render or Kubernetes, set:
```env
STORAGE_PROVIDER=s3
STORAGE_BUCKET=my-messenger-bucket
STORAGE_ACCESS_KEY=your_key
STORAGE_SECRET_KEY=your_secret
# For Cloudflare R2:
STORAGE_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
STORAGE_PUBLIC_URL_PREFIX=https://media.mydomain.com
```

---

## 12. Firebase Cloud Messaging (Push Notifications)

To enable push notifications when client apps are in the background or terminated:
1. In the Firebase Console, go to **Project Settings** > **Service Accounts**.
2. Click **Generate new private key** to download your JSON credential.
3. Configure the three environment variables in `.env`:
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_CLIENT_EMAIL`
   - `FIREBASE_PRIVATE_KEY` (Keep the `-----BEGIN PRIVATE KEY-----` and `\n` format)
4. When unset, the backend runs in **dry-run mode**, logging push messages safely without crashing.

---

## 13. Render Production Deployment (Step-by-Step)

### Option 1: Automatic Blueprint (One-Click)
1. Push this repository to GitHub or GitLab.
2. In the Render Dashboard, click **New +** > **Blueprint**.
3. Select your repository. Render reads `backend/render.yaml` and will automatically provision:
   - A managed PostgreSQL instance (`messenger-db`)
   - A Web Service (`messenger-backend`)
   - Auto-generated `JWT_SECRET` and internal database link.

### Option 2: Manual Setup on Render
1. **Create Managed PostgreSQL**:
   - In Render, click **New +** > **PostgreSQL**.
   - Name: `messenger-db`, User: `postgres`, Region: `Oregon` (or closest to you).
   - Once ready, copy the **Internal Database URL**.
2. **Create Web Service**:
   - In Render, click **New +** > **Web Service**.
   - Connect your GitHub repo.
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && alembic upgrade head`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/health`
3. **Configure Environment Variables in Render**:
   - `DATABASE_URL`: Paste the Internal Database URL from step 1.
   - `JWT_SECRET`: Generate a 64-char random hex string.
   - `JWT_ALGORITHM`: `HS256`
   - `CORS_ORIGINS`: `*`
   - `STUN_SERVER`: `stun:stun.l.google.com:19302`
   - `STORAGE_PROVIDER`: `local` (or `s3` with your R2/S3 bucket credentials).
4. Click **Deploy**. Render will build the image, run migrations, and launch your service!

---

## 14. Render Cold Start & Server Status

The backend is engineered for deployment on Render, where free-tier web services temporarily sleep when inactive. The mobile application detects server availability smoothly and waits gracefully while Render wakes up the service.

### Why the First Request May Be Slow (Cold Start)
On Render, inactive free-tier instances sleep after 15 minutes of zero incoming traffic to conserve resources. When the mobile app sends its first request, Render provisions a container, boots Python 3, initializes FastAPI, and opens the database connection pool. This cold-start spin-up typically takes **20 to 45 seconds**. Once the container is awake, all subsequent API and WebSocket requests respond in **tens of milliseconds**.

### Health Check Endpoint: `GET /health`
- **Exact URL**: `GET /health` (e.g., `https://my-messenger.onrender.com/health`)
- **Authentication**: **None required** (public, fast, lightweight probe)
- **Response Format** (when fully running):
  ```json
  {
    "status": "ok",
    "service": "messenger-backend"
  }
  ```
- **HTTP Status Code**: `200 OK`
- **Performance**: Instantaneous in-memory check without database queries or heavy computations.

### Server Startup Status
The backend tracks its lifecycle states without database polling:
- `starting`: Server is initializing upload directories, configurations, and connection pools.
- `online`: The normal operational state after FastAPI's lifespan startup has successfully completed.
- Diagnostic header: Responses from `/health` include `X-Server-Status: online` (or `starting`).
- Detailed status diagnostics are also accessible via `GET /api/server/status` or `GET /health?detailed=true`.

### How the Mobile App Handles Cold Starts
When the mobile app launches, it immediately sends a request to `GET /health`:

1. **Situation A — Backend is already awake**:
   - `/health` responds with `HTTP 200` in <100ms.
   - The app transitions immediately to the login or home screen.
2. **Situation B — Backend is sleeping / waking up**:
   - The initial request takes several seconds while Render boots.
   - The app remains on a clean loading screen and displays:
     > **"Please wait... Starting server..."**
3. **Situation C — Temporary connection failure**:
   - If the initial connection drops while the container is spinning up, the app automatically retries without user intervention.

### Recommended Client Retry Strategy
Mobile clients should implement staggered exponential retry to avoid spamming Render during boot:
- **Attempt 1**: Immediately upon app launch
- **Attempt 2**: Wait 2 seconds
- **Attempt 3**: Wait 4 seconds
- **Attempt 4**: Wait 6 seconds
- **Subsequent attempts**: Cap at 6-second intervals up to a maximum duration of **45 to 60 seconds**.

### Do Not Block the App Forever (Graceful Error Recovery)
The app must not remain on the loading screen indefinitely. If `/health` does not respond successfully after the maximum timeout (e.g., 45–60 seconds due to internet outage or Render service misconfiguration), the app transitions from the loading spinner to a clear error message:
> **"Unable to connect to server. Please try again."**
> 
> `[ 🔄 Retry ]` button

Tapping the retry button restarts the cold-start polling flow.

### Important Render Behavior & Flow
The backend **cannot send any notification while it is completely asleep**, because no server code or memory is executing. Instead, the real-world sequence is:

```
Mobile app opens
      ↓
Mobile app requests GET /health
      ↓
Render wakes backend container
      ↓
FastAPI backend starts & initializes
      ↓
/health returns HTTP 200 {"status": "ok", "service": "messenger-backend"}
      ↓
Mobile app detects server is online
      ↓
App continues to Login / Home screen
      ↓
Owner receives "🟢 Server is online"
```

### Personal Server-Online Notification (Owner Only)
When the backend wakes up and transitions to `online`, the backend is configured to notify **only the owner's account**:
- **Zero Broadcast to Regular Users**: Regular messenger contacts will never receive this notification.
- **Configurable via Environment Variable**: Set `OWNER_USERNAME=<username>` in your Render environment variables or `.env`.
- **No Hardcoded Secrets**: The backend never checks hardcoded passwords or secrets for the owner.
- **Event Concept**: The backend dispatches a `server:online` event over WebSockets:
  ```json
  {
    "event": "server:online",
    "data": {
      "service": "messenger-backend",
      "status": "online",
      "message": "🟢 Server is online",
      "timestamp": "2026-09-22T16:20:00Z"
    }
  }
  ```
- **Mobile Display**: When the owner's mobile app receives this event, it displays:
  > **"🟢 Server is online"**

---

## 15. Exact URLs the Mobile App Needs

Once your backend is deployed (for example, on `https://my-messenger.onrender.com`):

| Variable | Exact Render URL Format | Example |
|---|---|---|
| **API_BASE_URL** | `https://<service-name>.onrender.com` | `https://my-messenger.onrender.com` |
| **WEBSOCKET_URL** | `wss://<service-name>.onrender.com/ws` | `wss://my-messenger.onrender.com/ws` |
| **HEALTH_CHECK** | `https://<service-name>.onrender.com/health` | `https://my-messenger.onrender.com/health` |
| **SWAGGER_DOCS** | `https://<service-name>.onrender.com/docs` | `https://my-messenger.onrender.com/docs` |

> **IMPORTANT FOR MOBILE APP DEVELOPERS**:
> You **ONLY need to configure `API_BASE_URL`**.
> The mobile app code automatically constructs all child endpoints, including:
> `API_BASE_URL + "/health"`
> Never require end users or developers to manually enter the full health check URL.

---

## 16. Connecting the Mobile App

Create a single configuration file in your Flutter, React Native, or Swift/Kotlin app. Ready-to-copy client configurations with built-in cold start handlers are included in:
- `backend/config.dart` (Flutter / Dart)
- `backend/config.ts` (React Native / Expo / TypeScript)

### Flutter / Dart (`config.dart` snippet):

```dart
// The developer only sets apiBaseUrl:
class AppConfig {
  static const String apiBaseUrl = "https://my-messenger.onrender.com";

  // Automatically derived:
  static String get healthEndpoint => "$apiBaseUrl/health";
  static String get webSocketUrl => "wss://${Uri.parse(apiBaseUrl).host}/ws";
}

// Cold start listener:
final isOnline = await ServerLifecycleService.waitForServerOnline(
  onStatusUpdate: (status) => print(status), // "Starting server... Please wait..."
);
```

### TypeScript / React Native (`config.ts` snippet):

```typescript
// The developer only sets API_BASE_URL:
export const Config = {
  API_BASE_URL: "https://my-messenger.onrender.com",

  // Automatically derived:
  get HEALTH_URL() { return `${this.API_BASE_URL}/health`; },
  get WEBSOCKET_URL() { return `wss://${new URL(this.API_BASE_URL).host}/ws`; },
};

// Cold start listener:
const isOnline = await ServerColdStartManager.waitForServerOnline({
  onStatusUpdate: (msg) => setBanner(msg),
});
```

---

## 17. Troubleshooting Guide

- **Error: `connection refused` on PostgreSQL**: Ensure PostgreSQL is running and your `DATABASE_URL` uses the `postgresql+asyncpg://` scheme.
- **Render cold start delay**: If the service has been idle for >15 minutes, allow 30–45 seconds for `/health` to return `200 OK`. Ensure client uses the recommended retry strategy.
- **Owner notification not appearing**: Verify `OWNER_USERNAME` matches the logged-in owner's username exactly (case-insensitive).
- **WebSocket closes immediately with code 4001**: The JWT access token was missing or expired. Authenticate first with `POST /api/auth/login` and pass `?token=<access_token>` in the WebSocket URL.
- **WebRTC call connects but no audio/video**: Verify both clients can reach the STUN server (`stun:stun.l.google.com:19302`). If users are on restrictive cellular networks (Symmetric NAT), configure a TURN server.
- **Render file uploads disappear**: Render's free tier has an ephemeral disk. To preserve uploaded media across restarts, switch `STORAGE_PROVIDER=s3` with Cloudflare R2 or Amazon S3.

---

## 18. Mobile App Connection Values

| VALUE | WHERE TO GET IT | PUT IT IN APP? |
|---|---|:---:|
| **API_BASE_URL** | Your Render service URL (`https://...onrender.com`) | **YES (Only URL needed!)** |
| **WEBSOCKET_URL** | Automatically constructed from `API_BASE_URL` + `/ws` | **YES (Derived)** |
| **HEALTH_CHECK** | Automatically constructed from `API_BASE_URL` + `/health` | **YES (Derived)** |
| **STUN_SERVER** | WebRTC configuration (`stun:stun.l.google.com:19302`) | **YES** |
| **TURN_SERVER** | Optional TURN provider URL (e.g. Twilio, Metered.ca, Coturn) | **YES** |
| **TURN_USERNAME** | Optional TURN username (provided via `/api/calls/config`) | **YES** |
| **TURN_PASSWORD** | Optional TURN password / credential | **NO, if it is a backend secret** (fetch dynamically via `/api/calls/config`) |
| **DATABASE_URL** | Render PostgreSQL Internal Connection String | **NO (STRICT BACKEND SECRET)** |
| **JWT_SECRET** | Backend environment variable | **NO (STRICT BACKEND SECRET)** |
| **OWNER_USERNAME** | Backend environment variable | **NO (STRICT BACKEND SECRET)** |
| **FIREBASE_PRIVATE_KEY** | Firebase service account credentials | **NO (STRICT BACKEND SECRET)** |

---

Developed with craftsmanship for secure, private, real-time messaging.
