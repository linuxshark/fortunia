import axios, { AxiosInstance } from 'axios';

// All API calls go through the Next.js server-side proxy (/api/fortunia/...).
// The proxy injects the FORTUNIA_API_KEY — it is never exposed to the browser.
const client: AxiosInstance = axios.create({
  baseURL: '/api/fortunia',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ──────────────────────────────────────────────────────────────────────────────
// Types matching api/app/schemas/expense.py and api/app/schemas/reports.py
// ──────────────────────────────────────────────────────────────────────────────

export interface Expense {
  id: number;
  user_id: string;
  amount: number;
  currency: string;
  category_id: number | null;
  category_name: string | null;
  merchant_id: number | null;
  merchant_name: string | null;
  spent_at: string;
  note: string | null;
  source: string;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}

export interface CategorySummary {
  category: string;
  count: number;
  total: number;
  average: number;
  percentage: number;
}

export interface DayReport {
  date: string;
  total: number;
  currency: string;
  count: number;
  expenses: { id: number; amount: number }[];
}

export interface MonthReport {
  month: string;
  total: number;
  currency: string;
  count: number;
  by_category: CategorySummary[];
}

export interface CategoryReport {
  period: string;
  categories: CategorySummary[];
  total: number;
}

export interface TrendPoint {
  month: string;
  total: number;
  count: number;
}

export interface TrendReport {
  months: number;
  trend: TrendPoint[];
  average_monthly: number;
}

// ──────────────────────────────────────────────────────────────────────────────
// Expense endpoints
// ──────────────────────────────────────────────────────────────────────────────

export const fetchExpenses = async (
  userId: string,
  limit: number = 50,
  offset: number = 0,
  categoryId?: number,
  fromDate?: string,
  toDate?: string
): Promise<Expense[]> => {
  const params: Record<string, unknown> = { user_id: userId, limit, offset };
  if (categoryId != null) params.category_id = categoryId;
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;

  const { data } = await client.get('/expenses', { params });
  return data;
};

export const fetchExpenseById = async (id: number): Promise<Expense> => {
  const { data } = await client.get(`/expenses/${id}`);
  return data;
};

export const updateExpense = async (
  id: number,
  updates: Partial<Pick<Expense, 'amount' | 'category_id' | 'merchant_id' | 'note'>>
): Promise<Expense> => {
  const { data } = await client.patch(`/expenses/${id}`, updates);
  return data;
};

export const deleteExpense = async (id: number): Promise<void> => {
  await client.delete(`/expenses/${id}`);
};

// ──────────────────────────────────────────────────────────────────────────────
// Report endpoints
// ──────────────────────────────────────────────────────────────────────────────

export const fetchDayReport = async (userId: string): Promise<DayReport> => {
  const { data } = await client.get('/reports/today', {
    params: { user_id: userId },
  });
  return data;
};

export const fetchMonthReport = async (userId: string, ym?: string): Promise<MonthReport> => {
  const params: Record<string, string> = { user_id: userId };
  if (ym) params.ym = ym;
  const { data } = await client.get('/reports/month', { params });
  return data;
};

export const fetchCategoryReport = async (userId: string, period = 'month'): Promise<CategoryReport> => {
  const { data } = await client.get('/reports/categories', {
    params: { user_id: userId, period },
  });
  return data;
};

export const fetchTrendReport = async (userId: string, months: number = 6): Promise<TrendReport> => {
  const { data } = await client.get('/reports/trend', {
    params: { user_id: userId, months },
  });
  return data;
};

export const fetchTopMerchants = async (userId: string, limit: number = 10) => {
  const { data } = await client.get('/reports/top-merchants', {
    params: { user_id: userId, limit },
  });
  return data;
};

export default client;
