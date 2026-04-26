'use client';

import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, Legend, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { fetchCategoryReport } from '@/lib/api-client';

interface CategoryData {
  category: string;
  count: number;
  total_amount: number;
  percentage: number;
}

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

export default function Categories() {
  const [userId] = useState('default_user');
  const [categories, setCategories] = useState<CategoryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoading(true);
        const data = await fetchCategoryReport(userId);
        setCategories(data);
      } catch (err) {
        setError('Failed to load categories');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadCategories();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-lg text-gray-600">Loading categories...</p>
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

  const totalSpent = categories.reduce((sum, cat) => sum + cat.total_amount, 0);

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-gray-900">Category Breakdown</h1>

      {categories.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">No category data available yet.</p>
        </div>
      ) : (
        <>
          {/* Summary */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Total Spending by Category</h2>
            <p className="text-3xl font-bold text-primary mb-6">
              {totalSpent.toLocaleString('es-CL', {
                style: 'currency',
                currency: 'CLP',
                minimumFractionDigits: 0,
              })}
            </p>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Pie Chart */}
              <div>
                <h3 className="text-md font-semibold text-gray-900 mb-4">Distribution</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={categories}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ category, percentage }) => `${category} (${percentage}%)`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="total_amount"
                    >
                      {categories.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value) => `$${value.toLocaleString('es-CL')}`}
                      contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Bar Chart */}
              <div>
                <h3 className="text-md font-semibold text-gray-900 mb-4">Amount per Category</h3>
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
                    <YAxis stroke="#64748b" style={{ fontSize: '0.875rem' }} />
                    <Tooltip
                      formatter={(value) => `$${value.toLocaleString('es-CL')}`}
                      contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                    />
                    <Bar dataKey="total_amount" fill="#2563eb" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Category Table */}
          <div className="bg-white rounded-lg shadow overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Category</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase">Transactions</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Total</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Percentage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {categories.map((category, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                        ></div>
                        <span className="text-gray-900 capitalize">{category.category}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-center text-gray-600">{category.count}</td>
                    <td className="px-6 py-4 text-sm text-right text-gray-900 font-medium">
                      {category.total_amount.toLocaleString('es-CL', {
                        style: 'currency',
                        currency: 'CLP',
                        minimumFractionDigits: 0,
                      })}
                    </td>
                    <td className="px-6 py-4 text-sm text-right text-gray-900 font-medium">
                      {category.percentage}%
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
