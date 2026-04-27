'use client';

import { useEffect, useState } from 'react';
import {
  PieChart, Pie, Cell, Legend, Tooltip,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { fetchCategoryReport, CategorySummary } from '@/lib/api-client';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

const DEFAULT_USER = 'user';

export default function Categories() {
  const [userId] = useState(DEFAULT_USER);
  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [grandTotal, setGrandTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoading(true);
        const data = await fetchCategoryReport(userId);
        setCategories(data.categories);
        setGrandTotal(data.total);
      } catch (err) {
        setError('Error al cargar las categorías');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadCategories();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-lg text-gray-600">Cargando categorías...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
        <p>{error}</p>
      </div>
    );
  }

  const formatCLP = (v: number) =>
    v.toLocaleString('es-CL', { style: 'currency', currency: 'CLP', minimumFractionDigits: 0 });

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-gray-900">Categorías</h1>

      {categories.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">Sin datos de categorías aún.</p>
        </div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Gasto total por categoría</h2>
            <p className="text-3xl font-bold text-primary mb-6">{formatCLP(grandTotal)}</p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <h3 className="text-md font-semibold text-gray-900 mb-4">Distribución</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={categories}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ category, percentage }) => `${category} (${percentage.toFixed(1)}%)`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="total"
                    >
                      {categories.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => formatCLP(value)}
                      contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div>
                <h3 className="text-md font-semibold text-gray-900 mb-4">Monto por categoría</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={categories}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="category"
                      stroke="#64748b"
                      style={{ fontSize: '0.75rem' }}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis stroke="#64748b" style={{ fontSize: '0.875rem' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip
                      formatter={(value: number) => formatCLP(value)}
                      contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                    />
                    <Bar dataKey="total" name="Total" fill="#2563eb" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Categoría</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase">Transacciones</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Total</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Porcentaje</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {categories.map((cat, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                        />
                        <span className="text-gray-900">{cat.category}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-center text-gray-600">{cat.count}</td>
                    <td className="px-6 py-4 text-sm text-right text-gray-900 font-medium">
                      {formatCLP(cat.total)}
                    </td>
                    <td className="px-6 py-4 text-sm text-right text-gray-900 font-medium">
                      {cat.percentage.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
