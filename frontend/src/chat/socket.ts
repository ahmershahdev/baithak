export type ServerEvent =
  | { type: "subscribed"; channels: number[] }
  | { type: "message"; channel: number; event: number; message: unknown }
  | { type: "channel"; channel: number; data: unknown }
  | { type: "read"; channel: number; last_read_seq: number }
  | { type: "presence"; online: number[] }
  | { type: "notifications" }
  | { type: "presence_changes"; changes: { user: number; online: boolean }[] }
  | {
      type: "typing";
      channel: number;
      thread: number | null;
      user: { id: number; username: string; display_name: string };
    }
  | { type: "pong" };

export type Status = "connecting" | "open" | "reconnecting" | "closed";

// The server closes with these on purpose; reconnecting would only be refused again.
const FINAL_CODES = new Set([4401, 4404]);
const PING_EVERY = 25_000;

/** Delay before reconnect attempt n (0-based): 1 s doubling to 30 s, with up to 30% jitter so
 * a server restart is not met by every tab at the same instant. */
export function backoff(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(30_000, 1_000 * 2 ** attempt);
  return Math.round(base * (0.7 + 0.3 * random()));
}

export interface LiveSocketOptions {
  url: string;
  onEvent: (event: ServerEvent) => void;
  onStatus: (status: Status) => void;
  /** Called on every open after the first: the time to catch up on what was missed. */
  onReconnected: () => void;
  createSocket?: (url: string) => WebSocket;
}

export class LiveSocket {
  private socket: WebSocket | null = null;
  private attempt = 0;
  private everOpened = false;
  private stopped = false;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private pingTimer: ReturnType<typeof setInterval> | undefined;

  constructor(private readonly options: LiveSocketOptions) {
    this.connect();
  }

  /** Send while connected; false when the socket is down (a typing notice is simply lost). */
  send(payload: unknown): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(payload));
    return true;
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.retryTimer);
    clearInterval(this.pingTimer);
    this.socket?.close(1000);
    this.options.onStatus("closed");
  }

  private connect() {
    const create = this.options.createSocket ?? ((url: string) => new WebSocket(url));
    this.options.onStatus(this.everOpened ? "reconnecting" : "connecting");
    const socket = create(this.options.url);
    this.socket = socket;

    socket.addEventListener("open", () => {
      const reconnected = this.everOpened;
      this.everOpened = true;
      this.attempt = 0;
      this.options.onStatus("open");
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "ping" }));
      }, PING_EVERY);
      if (reconnected) this.options.onReconnected();
    });

    socket.addEventListener("message", (raw: MessageEvent<string>) => {
      try {
        this.options.onEvent(JSON.parse(raw.data) as ServerEvent);
      } catch {
        // Not JSON: nothing the server sends, so nothing to act on.
      }
    });

    socket.addEventListener("close", (closed: CloseEvent) => {
      clearInterval(this.pingTimer);
      if (this.stopped) return;
      if (FINAL_CODES.has(closed.code)) {
        this.options.onStatus("closed");
        return;
      }
      this.options.onStatus("reconnecting");
      this.retryTimer = setTimeout(() => {
        this.connect();
      }, backoff(this.attempt));
      this.attempt += 1;
    });
  }
}

export function socketUrl(slug: string): string {
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${window.location.host}/ws/workspaces/${encodeURIComponent(slug)}/`;
}
