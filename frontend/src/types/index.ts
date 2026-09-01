export type Priority = 'low' | 'medium' | 'high';

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiErrorBody | null;
}

export interface Board {
  id: number;
  name: string;
  description: string | null;
  color: string;
  is_active: boolean;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface BoardWithColumns extends Board {
  columns: ColumnWithTasks[];
}

export interface Column {
  id: number;
  board_id: number;
  name: string;
  position: number;
  is_done_column: boolean;
  created_at: string;
  updated_at: string;
}

export interface ColumnWithTasks extends Column {
  tasks: Task[];
}

export interface Task {
  id: number;
  column_id: number;
  title: string;
  description: string | null;
  priority: Priority;
  due_date: string | null;
  tags: string[];
  position: number;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskCreateInput {
  title: string;
  description?: string | null;
  priority?: Priority;
  due_date?: string | null;
  tags?: string[];
  column_id?: number;
  position?: number;
}

export interface TaskUpdateInput {
  title?: string;
  description?: string | null;
  priority?: Priority;
  due_date?: string | null;
  tags?: string[];
}

export interface BoardCreateInput {
  name: string;
  description?: string | null;
  color?: string;
  with_default_columns?: boolean;
  make_active?: boolean;
}

export interface BoardUpdateInput {
  name?: string;
  description?: string | null;
  color?: string;
}

export interface ColumnCreateInput {
  name: string;
  position?: number;
  is_done_column?: boolean;
}

export interface PriorityBreakdown {
  low: number;
  medium: number;
  high: number;
}

export interface ColumnCount {
  column_id: number;
  column_name: string;
  count: number;
}

export interface DailyCount {
  date: string;
  count: number;
}

export interface BoardStats {
  board_id: number;
  total_tasks: number;
  open_tasks: number;
  completed_tasks: number;
  completed_this_week: number;
  created_this_week: number;
  overdue_tasks: number;
  due_soon_tasks: number;
  by_priority: PriorityBreakdown;
  by_column: ColumnCount[];
  completion_trend: DailyCount[];
  top_tags: string[];
}

export type RealtimeEvent =
  | 'connected'
  | 'pong'
  | 'board.created'
  | 'board.updated'
  | 'board.activated'
  | 'board.deleted'
  | 'board.reordered'
  | 'column.created'
  | 'column.updated'
  | 'column.deleted'
  | 'column.reordered'
  | 'task.created'
  | 'task.updated'
  | 'task.moved'
  | 'task.deleted'
  | 'task.reordered';

export interface RealtimeMessage<T = unknown> {
  event: RealtimeEvent;
  board_id: number | null;
  data: T;
}
