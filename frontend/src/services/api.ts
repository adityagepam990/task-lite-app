import type {
  ApiResponse,
  Board,
  BoardCreateInput,
  BoardStats,
  BoardUpdateInput,
  BoardWithColumns,
  Column,
  ColumnCreateInput,
  Task,
  TaskCreateInput,
  TaskUpdateInput,
} from '@/types';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api';

export class ApiError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown> | null;

  constructor(message: string, code: string, status: number, details?: Record<string, unknown> | null) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      'Could not reach the server. Check that the backend is running and reachable.',
      'network_error',
      0,
    );
  }

  let body: ApiResponse<T> | null = null;
  try {
    body = await response.json();
  } catch {
    // Fall through to status-based error below.
  }

  if (!response.ok || !body || !body.success) {
    const error = body?.error;
    throw new ApiError(
      error?.message ?? `Request failed with status ${response.status}`,
      error?.code ?? 'unknown_error',
      response.status,
      error?.details,
    );
  }

  return body.data as T;
}

function toQuery(params: Record<string, string | number | boolean | string[] | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      value.forEach((v) => search.append(key, v));
    } else {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export const api = {
  boards: {
    list: () => request<Board[]>('/boards'),
    getActive: () => request<BoardWithColumns>('/boards/active'),
    get: (id: number) => request<BoardWithColumns>(`/boards/${id}`),
    create: (input: BoardCreateInput) =>
      request<BoardWithColumns>('/boards', { method: 'POST', body: JSON.stringify(input) }),
    update: (id: number, input: BoardUpdateInput) =>
      request<Board>(`/boards/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
    activate: (id: number) => request<BoardWithColumns>(`/boards/${id}/activate`, { method: 'POST' }),
    reorder: (boardIds: number[]) =>
      request<Board[]>('/boards/reorder', { method: 'PUT', body: JSON.stringify({ board_ids: boardIds }) }),
    delete: (id: number) => request<{ id: number }>(`/boards/${id}`, { method: 'DELETE' }),
  },
  columns: {
    list: (boardId: number) => request<Column[]>(`/boards/${boardId}/columns`),
    create: (boardId: number, input: ColumnCreateInput) =>
      request<Column>(`/boards/${boardId}/columns`, { method: 'POST', body: JSON.stringify(input) }),
    update: (id: number, input: Partial<ColumnCreateInput>) =>
      request<Column>(`/columns/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
    delete: (id: number) => request<{ id: number }>(`/columns/${id}`, { method: 'DELETE' }),
    reorder: (boardId: number, columnIds: number[]) =>
      request<Column[]>(`/boards/${boardId}/columns/reorder`, {
        method: 'PUT',
        body: JSON.stringify({ column_ids: columnIds }),
      }),
  },
  tasks: {
    search: (params: {
      boardId?: number;
      columnId?: number;
      q?: string;
      priority?: string[];
      tag?: string[];
      completed?: boolean;
      overdue?: boolean;
    }) =>
      request<Task[]>(
        `/tasks${toQuery({
          board_id: params.boardId,
          column_id: params.columnId,
          q: params.q,
          priority: params.priority,
          tag: params.tag,
          completed: params.completed,
          overdue: params.overdue,
        })}`,
      ),
    listInColumn: (columnId: number) => request<Task[]>(`/columns/${columnId}/tasks`),
    create: (columnId: number, input: TaskCreateInput) =>
      request<Task>(`/columns/${columnId}/tasks`, { method: 'POST', body: JSON.stringify(input) }),
    update: (id: number, input: TaskUpdateInput) =>
      request<Task>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(input) }),
    move: (id: number, columnId: number, position: number) =>
      request<Task>(`/tasks/${id}/move`, {
        method: 'POST',
        body: JSON.stringify({ column_id: columnId, position }),
      }),
    reorder: (columnId: number, taskIds: number[]) =>
      request<Task[]>(`/columns/${columnId}/tasks/reorder`, {
        method: 'PUT',
        body: JSON.stringify({ task_ids: taskIds }),
      }),
    delete: (id: number) => request<{ id: number }>(`/tasks/${id}`, { method: 'DELETE' }),
    boardTags: (boardId: number) => request<string[]>(`/boards/${boardId}/tags`),
  },
  stats: {
    active: () => request<BoardStats>('/stats'),
    forBoard: (boardId: number) => request<BoardStats>(`/boards/${boardId}/stats`),
  },
};
