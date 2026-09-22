// ==============================================================================
// Mobile App Configuration for React Native / Expo / TypeScript
// ==============================================================================
// Copy this file directly into your app project under src/config.ts
// ==============================================================================
// NOTE FOR DEVELOPERS:
// You only need to configure API_BASE_URL. The app automatically constructs
// all other URLs, including the health check: `${API_BASE_URL}/health`.
// ==============================================================================

export interface RTCServerConfig {
  urls: string | string[];
  username?: string;
  credential?: string;
}

export const Config = {
  /**
   * Base API URL of your backend.
   * You ONLY need to configure this single URL.
   *
   * For Local development:
   * - Android Emulator: "http://10.0.2.2:8000"
   * - iOS Simulator: "http://localhost:8000"
   * - Physical device on local WiFi: "http://192.168.x.x:8000"
   * For Render Production:
   * - "https://your-service-name.onrender.com"
   */
  API_BASE_URL: "https://your-service-name.onrender.com",

  /**
   * Real-time WebSocket URL automatically derived from API_BASE_URL.
   * ws:// for http and wss:// for https.
   */
  get WEBSOCKET_URL(): string {
    const url = new URL(this.API_BASE_URL);
    const protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${url.host}/ws`;
  },

  /**
   * Health check endpoint automatically derived: API_BASE_URL + "/health"
   * Lightweight, unauthenticated probe for Render cold start detection.
   */
  get HEALTH_URL(): string {
    return `${this.API_BASE_URL}/health`;
  },

  /**
   * Default WebRTC ICE servers (STUN) for peer-to-peer audio & video calling.
   * You can also fetch live STUN/TURN configurations via GET /api/calls/config
   */
  RTC_CONFIG: {
    iceServers: [
      { urls: "stun:stun.l.google.com:19302" },
      { urls: "stun:stun1.l.google.com:19302" },
    ] as RTCServerConfig[],
  },

  /**
   * Core REST Endpoints (path suffixes)
   */
  ENDPOINTS: {
    AUTH_LOGIN: "/api/auth/login",
    AUTH_REGISTER: "/api/auth/register",
    AUTH_ME: "/api/auth/me",
    USERS_SEARCH: "/api/users/search",
    CHATS: "/api/chats",
    MESSAGES: (chatId: number) => `/api/chats/${chatId}/messages`,
    MESSAGE_DELIVERED: (msgId: number) => `/api/messages/${msgId}/delivered`,
    CHAT_READ: (chatId: number) => `/api/chats/${chatId}/read`,
    FILE_UPLOAD: "/api/files/upload",
    CALLS_CONFIG: "/api/calls/config",
    CALLS_INITIATE: "/api/calls/initiate",
    CALLS_END: (callId: number) => `/api/calls/${callId}/end`,
    DEVICE_REGISTER: "/api/devices/register",
    HEALTH: "/health",
    SERVER_STATUS: "/api/server/status",
  },
};

/**
 * Render Cold-Start & Health Check Manager for Mobile Clients
 */
export class ServerColdStartManager {
  /**
   * Polls GET /health until the Render backend finishes waking up.
   *
   * Flow:
   * 1. Attempt immediately
   * 2. Retry after 2s, 4s, 6s (exponential backoff, avoids spamming server)
   * 3. Max timeout of 45 seconds
   * 4. Callbacks notify UI:
   *    - "Please wait... Starting server..."
   *    - If fails after timeout: "Unable to connect to server. Please try again."
   */
  static async waitForServerOnline(options?: {
    maxDurationMs?: number;
    onStatusUpdate?: (statusText: string) => void;
  }): Promise<boolean> {
    const maxDurationMs = options?.maxDurationMs ?? 45000;
    const onStatusUpdate = options?.onStatusUpdate;
    const startTime = Date.now();
    const retryDelays = [0, 2000, 4000, 6000, 6000];
    let attempt = 0;

    while (Date.now() - startTime < maxDurationMs) {
      const delay = attempt < retryDelays.length ? retryDelays[attempt] : 6000;
      if (delay > 0) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }

      attempt++;
      if (attempt > 1) {
        onStatusUpdate?.("Please wait... Starting server...");
      } else {
        onStatusUpdate?.("Connecting to server...");
      }

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);

        const res = await fetch(Config.HEALTH_URL, {
          method: "GET",
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (res.ok) {
          const data = await res.json();
          if (data.status === "ok") {
            onStatusUpdate?.("Online!");
            return true;
          }
        }
      } catch {
        // Network timeout / connection refused while container wakes up
      }
    }

    return false;
  }

  /**
   * Helper to inspect WebSocket events and extract owner-only "server:online" alert.
   * Only the account matching backend OWNER_USERNAME receives this event.
   */
  static handleWebSocketMessage(
    message: { event: string; data?: { message?: string; status?: string } },
    onOwnerAlert: (bannerText: string) => void,
  ) {
    if (message.event === "server:online") {
      const banner = message.data?.message ?? "🟢 Server is online";
      onOwnerAlert(banner);
    }
  }
}
