import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { FakeSocket } from "../test/fakeSocket";
import { backoff, LiveSocket, type ServerEvent, type Status } from "./socket";

describe("backoff", () => {
  test("doubles from one second up to thirty, with jitter below the base", () => {
    expect([0, 1, 2, 3, 4, 5, 9].map((n) => backoff(n, () => 1))).toEqual([
      1_000, 2_000, 4_000, 8_000, 16_000, 30_000, 30_000,
    ]);
    expect(backoff(0, () => 0)).toBe(700);
  });
});

describe("LiveSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeSocket);
    FakeSocket.all = [];
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function start() {
    const events: ServerEvent[] = [];
    const statuses: Status[] = [];
    const onReconnected = vi.fn();
    const live = new LiveSocket({
      url: "ws://test/ws/workspaces/team/",
      onEvent: (event) => events.push(event),
      onStatus: (status) => statuses.push(status),
      onReconnected,
      createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
    });
    return { live, events, statuses, onReconnected };
  }

  test("passes server events on", () => {
    const { events } = start();
    FakeSocket.latest().open();

    FakeSocket.latest().receive({ type: "pong" });

    expect(events).toEqual([{ type: "pong" }]);
  });

  test("a dropped socket reconnects with backoff and asks for catch-up only then", () => {
    const { statuses, onReconnected } = start();
    FakeSocket.latest().open();
    expect(onReconnected).not.toHaveBeenCalled();

    FakeSocket.latest().drop();
    expect(statuses.at(-1)).toBe("reconnecting");
    expect(FakeSocket.all).toHaveLength(1);
    vi.advanceTimersByTime(1_000);
    expect(FakeSocket.all).toHaveLength(2);
    FakeSocket.latest().open();

    expect(onReconnected).toHaveBeenCalledOnce();
    expect(statuses.at(-1)).toBe("open");
  });

  test("keeps trying with growing delays while the server is away", () => {
    start();
    FakeSocket.latest().drop();
    vi.advanceTimersByTime(1_000);
    FakeSocket.latest().drop();
    vi.advanceTimersByTime(1_000);
    expect(FakeSocket.all).toHaveLength(2);
    vi.advanceTimersByTime(1_000);

    expect(FakeSocket.all).toHaveLength(3);
  });

  test("does not reconnect when the server refuses on purpose", () => {
    const { statuses } = start();

    FakeSocket.latest().drop(4404);
    vi.advanceTimersByTime(60_000);

    expect(FakeSocket.all).toHaveLength(1);
    expect(statuses.at(-1)).toBe("closed");
  });

  test("pings so idle proxies keep the socket", () => {
    start();
    FakeSocket.latest().open();

    vi.advanceTimersByTime(25_000);

    expect(FakeSocket.latest().sent).toEqual([{ type: "ping" }]);
  });

  test("stop closes for good", () => {
    const { live } = start();
    FakeSocket.latest().open();

    live.stop();
    vi.advanceTimersByTime(60_000);

    expect(FakeSocket.all).toHaveLength(1);
  });
});
