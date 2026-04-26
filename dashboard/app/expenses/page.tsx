'use client';

import { useEffect, useState } from 'react';
import { fetchExpenses, Expense, updateExpense, deleteExpense } from '@/lib/api-client';
import { format, parseISO } from 'date-fns';

export default function Expenses() {
  const [userId] = useState('default_user');
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [category, setCategory] = useState<string>('');
  const [totalCount, setTotalCount] = useState(0);

  const categories = ['all', 'food', 'transport', 'entertainment', 'utilities', 'health', 'shopping', 'other'];

  useEffect(() => {
    const loadExpenses = async () => {
      try {
        setLoading(true);
        const data = await fetchExpenses(
          userId,
          limit,
          offset,
          category && category !== 'all' ? category : undefined
        );
        setExpenses(data);
        setTotalCount(data.length);
      } catch (err) {
        setError('Failed to load expenses');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadExpenses();
  }, [userId, limit, offset, category]);

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setCategory(e.target.value);
    setOffset(0);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this expense?')) return;
    try {
      await deleteExpense(id);
      setExpenses(expenses.filter((e) => e.id !== id));
    } catch (err) {
      setError('Failed to delete expense');
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-lg text-gray-600">Loading expenses...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Expenses</h1>
        <select
          value={category}
          onChange={handleCategoryChange}
          className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
        >
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          <p>{error}</p>
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        {expenses.length > 0 ? (
          <table className="min-w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Merchant</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Category</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Description</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Amount</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase">Confidence</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {expenses.map((expense) => (
                <tr key={expense.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {format(parseISO(expense.spent_at), 'dd/MM/yyyy HH:mm')}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{expense.merchant || '—'}</td>
                  <td className="px-6 py-4 text-sm">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {expense.category}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{expense.description || '—'}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right font-medium">
                    {expense.amount.toLocaleString('es-CL', {
                      style: 'currency',
                      currency: expense.currency,
                      minimumFractionDigits: 0,
                    })}
                  </td>
                  <td className="px-6 py-4 text-sm text-center">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        expense.confidence > 0.8
                          ? 'bg-green-100 text-green-800'
                          : expense.confidence > 0.6
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {Math.round(expense.confidence * 100)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center text-sm">
                    <button
                      onClick={() => handleDelete(expense.id)}
                      className="text-red-600 hover:text-red-900 font-medium"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center">
            <p className="text-gray-600">No expenses found.</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-600">Showing {expenses.length} of {totalCount} expenses</p>
        <div className="space-x-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={expenses.length < limit}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
