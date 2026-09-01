import type { RealtimeEvent, RealtimeMessage } from '@/types';

const WS_URL = process.env.EXPO_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws';

type Listener = (message: RealtimeMessage) => void;

/**
 * Thin reconnecting wrapper around the backend's /ws endpoint.
 *
 * Callers don't need to know the exact shape of every event payload --
 * they subscribe to event *names* and re-fetch whatever they need, which
 * keeps this client decoupled from the backend's broadcast payload shapes.
 */
class RealtimeClient {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private boardId: number | null = null;
  private reconnectDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedByClient = false;

  connect(boardId: number | null): void {
    this.boardId = boardId;
    this.closedByClient = false;
    this.open();
  }

  private open(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();

    const url = this.boardId != null ? `${WS_URL}?board_id=${this.boardId}` : WS_URL;
    const socket = new WebSocket(url);

    socket.onopen = () => {
      this.reconnectDelay = 1000;
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as RealtimeMessage;
        this.listeners.forEach((listener) => listener(message));
      } catch {
        // Ignore malformed frames.
      }
    };
    socket.onclose = () => {
      if (this.closedByClient) return;
      this.reconnectTimer = setTimeout(() => this.open(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15000);
    };
    socket.onerror = () => {
      socket.close();
    };

    this.socket = socket;
  }

  setBoardId(boardId: number | null): void {
    if (boardId === this.boardId) return;
    this.boardId = boardId;
    this.open();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  disconnect(): void {
    this.closedByClient = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.socket = null;
  }
}

export const realtime = new RealtimeClient();

export const BOARD_AFFECTING_EVENTS: RealtimeEvent[] = [
  'column.created',
  'column.updated',
  'column.deleted',
  'column.reordered',
  'task.created',
  'task.updated',
  'task.moved',
  'task.deleted',
  'task.reordered',
];

export const BOARD_LIST_AFFECTING_EVENTS: RealtimeEvent[] = [
  'board.created',
  'board.updated',
  'board.activated',
  'board.deleted',
  'board.reordered',
];
