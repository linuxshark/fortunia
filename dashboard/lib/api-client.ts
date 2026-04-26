import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const client: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'X-Internal-Key': process.env.NEXT_PUBLIC_API_KEY || '',
  },
});

export interface Expense {
  id: string;
  user_id: string;
  amount: number;
  currency: string;
  category: string;
  merchant: string | null;
  description: string | null;
  spent_at: string;
  created_at: string;
  confidence: number;
}

export interface CategorySummary {
  category: string;
  count: number;
  total_amount: number;
  percentage: number;
}

export interface DayReport {
  date: string;
  total_amount: number;
  count: number;
  top_category: string;
}

export interface MonthReport {
  month: string;
  total_amount: number;
  count: number;
  avg_expense: number;
}

export const fetchExpenses = async (
  userId: string,
  limit: number = 50,
  offset: number = 0,
  category?: string,
  fromDate?: string,
  toDate?: string
): Promise<Expense[]> => {
  const params: any = { limit, offset };
  if (category) params.category = category;
  if (fromDate) params.from = fromDate;
  if (toDate) params.to = toDate;

  const { data } = await client.get(`/expenses`, {
    params: { user_id: userId, ...params },
  });
  return data;
};

export const fetchExpenseById = async (id: string): Promise<Expense> => {
  const { data } = await client.get(`/expenses/${id}`);
  return data;
};

export const updateExpense = async (
  id: string,
  updates: Partial<Expense>
): Promise<Expense> => {
  const { data } = await client.patch(`/expenses/${id}`, updates);
  return data;
};

export const deleteExpense = async (id: string): Promise<void> => {
  await client.delete(`/expenses/${id}`);
};

export const fetchDayReport = async (userId: string, date: string) => {
  const { data } = await client.get(`/reports/today`, {
    params: { user_id: userId, date },
  });
  return data;
};

export const fetchMonthReport = async (userId: string, month: string) => {
  const { data } = await client.get(`/reports/month`, {
    params: { user_id: userId, month },
  });
  return data;
};

export const fetchCategoryReport = async (userId: string) => {
  const { data } = await client.get(`/reports/categories`, {
    params: { user_id: userId },
  });
  return data;
};

export const fetchTrendReport = async (userId: string, days: number = 30) => {
  const { data } = await client.get(`/reports/trend`, {
    params: { user_id: userId, days },
  });
  return data;
};

export const fetchTopMerchants = async (
  userId: string,
  limit: number = 10
) => {
  const { data } = await client.get(`/reports/top-merchants`, {
    params: { user_id: userId, limit },
  });
  return data;
};

export default client;
