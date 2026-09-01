import { create } from 'zustand';
import { api, ApiError } from '@/services/api';
import { BOARD_AFFECTING_EVENTS, BOARD_LIST_AFFECTING_EVENTS, realtime } from '@/services/realtime';
import type {
  Board,
  BoardCreateInput,
  BoardUpdateInput,
  BoardWithColumns,
  ColumnCreateInput,
  ColumnWithTasks,
  Task,
  TaskCreateInput,
  TaskUpdateInput,
} from '@/types';

interface BoardState {
  boards: Board[];
  activeBoard: BoardWithColumns | null;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;

  init: () => Promise<void>;
  refresh: () => Promise<void>;
  selectBoard: (boardId: number) => Promise<void>;
  createBoard: (input: BoardCreateInput) => Promise<Board>;
  updateBoard: (id: number, input: BoardUpdateInput) => Promise<void>;
  deleteBoard: (id: number) => Promise<void>;
  reorderBoards: (boardIds: number[]) => Promise<void>;

  createColumn: (input: ColumnCreateInput) => Promise<void>;
  updateColumn: (id: number, input: Partial<ColumnCreateInput>) => Promise<void>;
  deleteColumn: (id: number) => Promise<void>;
  reorderColumns: (columnIds: number[]) => Promise<void>;

  createTask: (columnId: number, input: TaskCreateInput) => Promise<void>;
  updateTask: (id: number, input: TaskUpdateInput) => Promise<void>;
  moveTask: (taskId: number, toColumnId: number, position: number) => Promise<void>;
  reorderTasks: (columnId: number, taskIds: number[]) => Promise<void>;
  deleteTask: (id: number) => Promise<void>;
}

let realtimeUnsubscribe: (() => void) | null = null;
let refetchTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleRefetch(fn: () => void) {
  if (refetchTimer) clearTimeout(refetchTimer);
  refetchTimer = setTimeout(fn, 150);
}

function withColumn(
  board: BoardWithColumns,
  columnId: number,
  updater: (column: ColumnWithTasks) => ColumnWithTasks,
): BoardWithColumns {
  return {
    ...board,
    columns: board.columns.map((c) => (c.id === columnId ? updater(c) : c)),
  };
}

export const useBoardStore = create<BoardState>((set, get) => ({
  boards: [],
  activeBoard: null,
  isLoading: false,
  isRefreshing: false,
  error: null,

  init: async () => {
    set({ isLoading: true, error: null });
    try {
      const [boards, activeBoard] = await Promise.all([api.boards.list(), api.boards.getActive()]);
      set({ boards, activeBoard, isLoading: false });
      realtime.connect(activeBoard.id);

      if (!realtimeUnsubscribe) {
        realtimeUnsubscribe = realtime.subscribe((message) => {
          if (BOARD_AFFECTING_EVENTS.includes(message.event)) {
            const current = get().activeBoard;
            if (current) {
              scheduleRefetch(() => {
                api.boards.get(current.id).then((fresh) => set({ activeBoard: fresh })).catch(() => {});
              });
            }
          }
          if (BOARD_LIST_AFFECTING_EVENTS.includes(message.event)) {
            scheduleRefetch(() => {
              api.boards.list().then((fresh) => set({ boards: fresh })).catch(() => {});
            });
          }
        });
      }
    } catch (err) {
      set({ isLoading: false, error: err instanceof ApiError ? err.message : 'Failed to load boards.' });
    }
  },

  refresh: async () => {
    const { activeBoard } = get();
    set({ isRefreshing: true });
    try {
      const [boards, fresh] = await Promise.all([
        api.boards.list(),
        activeBoard ? api.boards.get(activeBoard.id) : api.boards.getActive(),
      ]);
      set({ boards, activeBoard: fresh, isRefreshing: false });
    } catch {
      set({ isRefreshing: false });
    }
  },

  selectBoard: async (boardId) => {
    const board = await api.boards.activate(boardId);
    const boards = await api.boards.list();
    set({ activeBoard: board, boards });
    realtime.setBoardId(board.id);
  },

  createBoard: async (input) => {
    const board = await api.boards.create(input);
    const boards = await api.boards.list();
    set({ boards });
    if (input.make_active) {
      set({ activeBoard: board as BoardWithColumns });
      realtime.setBoardId(board.id);
    }
    return board;
  },

  updateBoard: async (id, input) => {
    const previous = get().boards;
    set({ boards: previous.map((b) => (b.id === id ? { ...b, ...input } as Board : b)) });
    try {
      await api.boards.update(id, input);
      const boards = await api.boards.list();
      const activeBoard = get().activeBoard;
      set({ boards, activeBoard: activeBoard && activeBoard.id === id ? { ...activeBoard, ...input } : activeBoard });
    } catch (err) {
      set({ boards: previous });
      throw err;
    }
  },

  deleteBoard: async (id) => {
    await api.boards.delete(id);
    const boards = await api.boards.list();
    const active = await api.boards.getActive();
    set({ boards, activeBoard: active });
    realtime.setBoardId(active.id);
  },

  reorderBoards: async (boardIds) => {
    const previous = get().boards;
    const reordered = boardIds
      .map((id) => previous.find((b) => b.id === id))
      .filter((b): b is Board => Boolean(b))
      .map((b, i) => ({ ...b, position: i }));
    set({ boards: reordered });
    try {
      await api.boards.reorder(boardIds);
    } catch (err) {
      set({ boards: previous });
      throw err;
    }
  },

  createColumn: async (input) => {
    const board = get().activeBoard;
    if (!board) return;
    await api.columns.create(board.id, input);
    const fresh = await api.boards.get(board.id);
    set({ activeBoard: fresh });
  },

  updateColumn: async (id, input) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;
    set({ activeBoard: withColumn(board, id, (c) => ({ ...c, ...input })) });
    try {
      await api.columns.update(id, input);
      const fresh = await api.boards.get(board.id);
      set({ activeBoard: fresh });
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },

  deleteColumn: async (id) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;
    set({ activeBoard: { ...board, columns: board.columns.filter((c) => c.id !== id) } });
    try {
      await api.columns.delete(id);
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },

  reorderColumns: async (columnIds) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;
    const reordered = columnIds
      .map((id) => board.columns.find((c) => c.id === id))
      .filter((c): c is ColumnWithTasks => Boolean(c))
      .map((c, i) => ({ ...c, position: i }));
    set({ activeBoard: { ...board, columns: reordered } });
    try {
      await api.columns.reorder(board.id, columnIds);
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },

  createTask: async (columnId, input) => {
    const board = get().activeBoard;
    if (!board) return;
    const tempId = -Date.now();
    const optimisticTask: Task = {
      id: tempId,
      column_id: columnId,
      title: input.title,
      description: input.description ?? null,
      priority: input.priority ?? 'medium',
      due_date: input.due_date ?? null,
      tags: input.tags ?? [],
      position: board.columns.find((c) => c.id === columnId)?.tasks.length ?? 0,
      is_completed: false,
      completed_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    set({ activeBoard: withColumn(board, columnId, (c) => ({ ...c, tasks: [...c.tasks, optimisticTask] })) });
    try {
      const created = await api.tasks.create(columnId, input);
      const latest = get().activeBoard;
      if (latest) {
        set({
          activeBoard: withColumn(latest, columnId, (c) => ({
            ...c,
            tasks: c.tasks.map((t) => (t.id === tempId ? created : t)),
          })),
        });
      }
    } catch (err) {
      const latest = get().activeBoard;
      if (latest) {
        set({
          activeBoard: withColumn(latest, columnId, (c) => ({
            ...c,
            tasks: c.tasks.filter((t) => t.id !== tempId),
          })),
        });
      }
      throw err;
    }
  },

  updateTask: async (id, input) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;
    set({
      activeBoard: {
        ...board,
        columns: board.columns.map((c) => ({
          ...c,
          tasks: c.tasks.map((t) => (t.id === id ? { ...t, ...input } : t)),
        })),
      },
    });
    try {
      const updated = await api.tasks.update(id, input);
      const latest = get().activeBoard;
      if (latest) {
        set({
          activeBoard: {
            ...latest,
            columns: latest.columns.map((c) => ({
              ...c,
              tasks: c.tasks.map((t) => (t.id === id ? updated : t)),
            })),
          },
        });
      }
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },

  moveTask: async (taskId, toColumnId, position) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;

    let moving: Task | undefined;
    const stripped = board.columns.map((c) => {
      const found = c.tasks.find((t) => t.id === taskId);
      if (found) moving = found;
      return { ...c, tasks: c.tasks.filter((t) => t.id !== taskId) };
    });
    if (!moving) return;

    const clampedColumns = stripped.map((c) => {
      if (c.id !== toColumnId) return c;
      const index = Math.max(0, Math.min(position, c.tasks.length));
      const tasks = [...c.tasks];
      tasks.splice(index, 0, { ...moving!, column_id: toColumnId, position: index });
      return { ...c, tasks: tasks.map((t, i) => ({ ...t, position: i })) };
    });

    set({ activeBoard: { ...board, columns: clampedColumns } });
    try {
      await api.tasks.move(taskId, toColumnId, position);
      const fresh = await api.boards.get(board.id);
      set({ activeBoard: fresh });
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },

  reorderTasks: async (columnId, taskIds) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;
    set({
      activeBoard: withColumn(board, columnId, (c) => {
        const byId = new Map(c.tasks.map((t) => [t.id, t]));
        const reordered = taskIds
          .map((id, i) => {
            const t = byId.get(id);
            return t ? { ...t, position: i } : undefined;
          })
          .filter((t): t is Task => Boolean(t));
        return { ...c, tasks: reordered };
      }),
    });
    try {
      await api.tasks.reorder(columnId, taskIds);
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },

  deleteTask: async (id) => {
    const board = get().activeBoard;
    if (!board) return;
    const previous = board;
    set({
      activeBoard: {
        ...board,
        columns: board.columns.map((c) => ({ ...c, tasks: c.tasks.filter((t) => t.id !== id) })),
      },
    });
    try {
      await api.tasks.delete(id);
    } catch (err) {
      set({ activeBoard: previous });
      throw err;
    }
  },
}));
