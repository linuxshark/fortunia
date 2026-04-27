'use client';

import { useEffect, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  fetchDayReport,
  fetchMonthReport,
  fetchTrendReport,
  fetchCategoryReport,
  fetchTopMerchants,
  DayReport,
  MonthReport,
  TrendReport,
  CategoryReport,
} from '@/lib/api-client';
import { format } from 'date-fns';

const DEFAULT_USER = 'user';

export default function Overview() {
  const [userId] = useState(DEFAULT_USER);
  const [dayReport, setDayReport] = useState<DayReport | null>(null);
  const [monthReport, setMonthReport] = useState<MonthReport | null>(null);
  const [trendData, setTrendData] = useState<TrendReport | null>(null);
  const [categoryData, setCategoryData] = useState<CategoryReport | null>(null);
  const [topMerchants, setTopMerchants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const ym = format(new Date(), 'yyyy-MM');

        const [day, month, trend, categories, merchants] = await Promise.all([
          fetchDayReport(userId).catch(() => null),
          fetchMonthReport(userId, ym).catch(() => null),
          fetchTrendReport(userId, 6).catch(() => null),
          fetchCategoryReport(userId).catch(() => null),
          fetchTopMerchants(userId, 5).catch(() => ({ merchants: [] })),
        ]);

        setDayReport(day);
        setMonthReport(month);
        setTrendData(trend);
        setCategoryData(categories);
        setTopMerchants(merchants?.merchants ?? []);
      } catch (err) {
        setError('Error al cargar el dashboard');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-lg text-gray-600">Cargando dashboard...</p>
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

  const avgExpense =
    monthReport && monthReport.count > 0
      ? monthReport.total / monthReport.count
      : 0;

  const topCategoryToday =
    dayReport && dayReport.count > 0 ? '—' : '—';

  const formatCLP = (v: number) =>
    v.toLocaleString('es-CL', { style: 'currency', currency: 'CLP', minimumFractionDigits: 0 });

  return (
    <div className="space-y-8">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Gasto de hoy</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {dayReport ? formatCLP(dayReport.total) : '$0'}
          </p>
          <p className="text-gray-600 text-xs mt-2">{dayReport?.count ?? 0} transacciones</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Este mes</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {monthReport ? formatCLP(monthReport.total) : '$0'}
          </p>
          <p className="text-gray-600 text-xs mt-2">{monthReport?.count ?? 0} transacciones</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Promedio por gasto</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {formatCLP(avgExpense)}
          </p>
          <p className="text-gray-600 text-xs mt-2">Este mes</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 text-sm font-medium">Promedio mensual</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {trendData ? formatCLP(trendData.average_monthly) : '$0'}
          </p>
          <p className="text-gray-600 text-xs mt-2">Últimos {trendData?.months ?? 6} meses</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Trend Chart */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Tendencia mensual</h2>
          {trendData && trendData.trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#64748b" style={{ fontSize: '0.875rem' }} />
                <YAxis stroke="#64748b" style={{ fontSize: '0.875rem' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                  formatter={(value: number) => formatCLP(value)}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Total"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ fill: '#2563eb', r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-600 text-center py-8">Sin datos disponibles</p>
          )}
        </div>

        {/* Category Distribution */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Distribución por categoría</h2>
          {categoryData && categoryData.categories.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={categoryData.categories}>
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
                  contentStyle={{ backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1' }}
                  formatter={(value: number) => formatCLP(value)}
                />
                <Bar dataKey="total" name="Total" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-600 text-center py-8">Sin datos disponibles</p>
          )}
        </div>
      </div>

      {/* Top Merchants */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Top comercios</h2>
        {topMerchants.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Comercio</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Transacciones</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-700 uppercase">Total</th>
                </tr>
              </thead>
              <tbody>
                {topMerchants.map((m, idx) => (
                  <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-900">{m.merchant || 'Desconocido'}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{m.count}</td>
                    <td className="px-6 py-4 text-sm text-gray-900 text-right font-medium">
                      {formatCLP(m.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-center py-8">Sin comercios registrados</p>
        )}
      </div>
    </div>
  );
}
