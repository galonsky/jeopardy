import { useEffect } from "react";

export function useWebSocket(onMessage: (message: unknown) => void) {
  useEffect(() => {
    let socket: WebSocket | undefined;
    let retryTimer: number | undefined;
    let closed = false;
    let attempt = 0;

    const connect = () => {
      if (closed) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/jobs/`);
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onmessage = (event) => {
        try {
          onMessage(JSON.parse(event.data));
        } catch {
          /* Ignore malformed job events. */
        }
      };
      socket.onclose = (event) => {
        if (event.code === 4003) {
          window.location.assign("/oidc/login/");
          return;
        }
        attempt += 1;
        const cap = Math.min(30_000, 1_000 * 2 ** Math.min(attempt, 5));
        retryTimer = window.setTimeout(connect, cap * (0.75 + Math.random() * 0.5));
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [onMessage]);
}
