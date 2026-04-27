'use client';

import { useEffect, useState } from 'react';
import { fetchExpenses, Expense, updateExpense, deleteExpense } from '@/lib/api-client';
import { format, parseISO } from 'date-fns';

const DEFAULT_USER = 'user';

export default function Expenses() {
  const [userId] = useState(DEFAULT_USER);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const loadExpenses = async () => {
      try {
        setLoading(true);
        const data = await fetchExpenses(userId, limit, offset);
        setExpenses(data);
      } catch (err) {
        setError('Error al cargar los gastos');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadExpenses();
  }, [userId, limit, offset]);

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este gasto?')) return;
    try {
      await deleteExpense(id);
      setExpenses(expenses.filter((e) => e.id !== id));
    } catch (err) {
      setError('Error al eliminar el gasto');
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-lg text-gray-600">Cargando gastos...</p>
      </div>
    );
  }

  const formatCLP = (amount: number, currency = 'CLP') =>
    amount.toLocaleString('es-CL', { style: 'currency', currency, minimumFractionDigits: 0 });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Gastos</h1>
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
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Fecha</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Comercio</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Categoría</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Nota</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Monto</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase">Confianza</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {expenses.map((expense) => (
                <tr key={expense.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {format(parseISO(expense.spent_at), 'dd/MM/yyyy HH:mm')}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{expense.merchant_name || '—'}</td>
                  <td className="px-6 py-4 text-sm">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {expense.category_name || 'Otros'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{expense.note || '—'}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right font-medium">
                    {formatCLP(expense.amount, expense.currency)}
                  </td>
                  <td className="px-6 py-4 text-sm text-center">
                    {expense.confidence != null ? (
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
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-6 py-4 text-center text-sm">
                    <button
                      onClick={() => handleDelete(expense.id)}
                      className="text-red-600 hover:text-red-900 font-medium"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center">
            <p className="text-gray-600">No hay gastos registrados.</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-600">Mostrando {expenses.length} gastos</p>
        <div className="space-x-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Anterior
          </button>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={expenses.length < limit}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Siguiente
          </button>
        </div>
      </div>
    </div>
  );
}
