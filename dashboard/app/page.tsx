'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import {
  fetchDayReport,
  fetchMonthReport,
  fetchTrendReport,
  fetchCategoryReport,
  fetchTopMerchants,
  DayReport,
  MonthReport,
  CategorySummary,
} from '@/lib/api-client';
import { format } from 'date-fns';

export default function Overview() {
  const [userId] = useState('default_user');
  const [dayReport, setDayReport] = useState<any>(null);
  const [monthReport, setMonthReport] = useState<MonthReport | null>(null);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [categoryData, setCategoryData] = useState<CategorySummary[]>([]);
  const [topMerchants, setTopMerchants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const today = format(new Date(), 'yyyy-MM-dd');
        const month = format(new Date(), 'yyyy-MM');

        const [day, month_report, trend, categories, merchants] = await Promise.all([
          fetchDayReport(userId, today).catch(() => null),
          fetchMonthReport(userId, month).catch(() => null),
          fetchTrendReport(userId, 30).catch(() => []),
          fetchCategoryReport(userId).catch(() => []),
          fetchTopMerchants(userId, 5).catch(() => []),
        ]);

        setDayReport(day);
        setMonthReport(month_report);
        setTrendData(trend);
        setCategoryData(categories);
        setTopMerchants(merchants);
      } catch (err) {
        setError('Failed to load dashboard data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-lg text-gray-600">Loading dashboard...</p>
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

  return (
    <div className="space-y-8">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Today's Spending</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {dayReport?.total_amount.toLocaleString('es-CL', {
              style: 'currency',
              currency: 'CLP',
              minimumFractionDigits: 0,
            }) || '$0'}
          </p>
          <p className="text-gray-600 text-xs mt-2">{dayReport?.count || 0} transactions</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">This Month</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {monthReport?.total_amount.toLocaleString('es-CL', {
              style: 'currency',
              currency: 'CLP',
              minimumFractionDigits: 0,
            }) || '$0'}
          </p>
          <p className="text-gray-600 text-xs mt-2">{monthReport?.count || 0} transactions</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Monthly Avg</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {monthReport?.avg_expense.toLocaleString('es-CL', {
              style: 'currency',
              currency: 'CLP',
              minimumFractionDigits: 0,
            }) || '$0'}
          </p>
          <p className="text-gray-600 text-xs mt-2">Per transaction</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Top Category</p>
          <p className="text-2xl font-bold text-primary mt-2 capitalize">
            {dayReport?.top_category || '—'}
          </p>
          <p className="text-gray-600 text-xs mt-2">Today's top</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trend Chart */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">30-Day Trend</h2>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#64748b" style={{ fontSize: '0.875rem' }} />
                <YAxis stroke="#64748b" style={{ fontSize: '0.875rem' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                  formatter={(value) => `$${value.toLocaleString('es-CL')}`}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ fill: '#2563eb', r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-600 text-center py-8">No data available</p>
          )}
        </div>

        {/* Category Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Category Distribution</h2>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={categoryData}>
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
                  contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                  formatter={(value) => `$${value.toLocaleString('es-CL')}`}
                />
                <Bar dataKey="total_amount" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-600 text-center py-8">No data available</p>
          )}
        </div>
      </div>

      {/* Top Merchants */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Top Merchants</h2>
        {topMerchants.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Merchant</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Transactions</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Total</th>
                </tr>
              </thead>
              <tbody>
                {topMerchants.map((merchant, idx) => (
                  <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-900">{merchant.merchant || 'Unknown'}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{merchant.count}</td>
                    <td className="px-6 py-4 text-sm text-gray-900 text-right font-medium">
                      {merchant.total_amount.toLocaleString('es-CL', {
                        style: 'currency',
                        currency: 'CLP',
                        minimumFractionDigits: 0,
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-center py-8">No merchants found</p>
        )}
      </div>
    </div>
  );
}
