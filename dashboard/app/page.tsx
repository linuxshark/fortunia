'use client';

import { useEffect, useState, useCallback } from 'react';
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
  fetchMonthlyBalance,
  DayReport,
  MonthReport,
  TrendReport,
  CategoryReport,
  MonthlyBalance,
} from '@/lib/api-client';
import { format } from 'date-fns';
import MonthNavigator from './components/MonthNavigator';
import UserFilter from './components/UserFilter';
import BalanceCard from './components/BalanceCard';

const formatCLP = (v: number) => {
  const abs = Math.abs(Math.round(v));
  const formatted = abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return v < 0 ? `-$${formatted}` : `$${formatted}`;
};

const tickCLP = (v: number) => {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
};

const CHART_COLORS = {
  line: '#3b6ef8',
  bar:  '#3b6ef8',
  grid: 'var(--border)',
  axis: 'var(--text-muted)',
};

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
      <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
        {label}
      </p>
      <p className="text-2xl font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
        {value}
      </p>
      {sub && (
        <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>
          {sub}
        </p>
      )}
    </div>
  );
}

export default function Resumen() {
  const [userId, setUserId] = useState('all');
  const [activeMonth, setActiveMonth] = useState(format(new Date(), 'yyyy-MM'));
  const [dayReport, setDayReport] = useState<DayReport | null>(null);
  const [monthReport, setMonthReport] = useState<MonthReport | null>(null);
  const [trendData, setTrendData] = useState<TrendReport | null>(null);
  const [categoryData, setCategoryData] = useState<CategoryReport | null>(null);
  const [topMerchants, setTopMerchants] = useState<any[]>([]);
  const [balance, setBalance] = useState<MonthlyBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [day, month, trend, categories, merchants, bal] = await Promise.all([
        fetchDayReport(userId).catch(() => null),
        fetchMonthReport(userId, activeMonth).catch(() => null),
        fetchTrendReport(userId, 6).catch(() => null),
        fetchCategoryReport(userId).catch(() => null),
        fetchTopMerchants(userId, 5).catch(() => ({ merchants: [] })),
        fetchMonthlyBalance(userId, activeMonth).catch(() => null),
      ]);
      setDayReport(day);
      setMonthReport(month);
      setTrendData(trend);
      setCategoryData(categories);
      setTopMerchants(merchants?.merchants ?? []);
      setBalance(bal);
    } catch {
      setError('Error al cargar el dashboard');
    } finally {
      setLoading(false);
    }
  }, [userId, activeMonth]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) {
    return (
      <div className="flex flex-col gap-4 animate-pulse">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl" style={{ backgroundColor: 'var(--bg-card)' }} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl p-5 text-sm" style={{ backgroundColor: '#2d1a1a', color: '#E85D24', border: '1px solid #6b2a1a' }}>
        {error}
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <MonthNavigator value={activeMonth} onChange={setActiveMonth} />
          <div className="flex items-center gap-3">
            <UserFilter value={userId} onChange={setUserId} />
          </div>
        </div>

        {/* Balance cards */}
        <BalanceCard
          totalIncome={balance?.total_income ?? 0}
          totalExpenses={balance?.total_expenses ?? 0}
          balance={balance?.balance ?? 0}
        />

        {/* KPI row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Saldo"
            value={dayReport ? formatCLP(dayReport.total) : '$0'}
            sub={`${dayReport?.count ?? 0} transacciones`}
          />
          <KpiCard
            label="Total del mes"
            value={monthReport ? formatCLP(monthReport.total) : '$0'}
            sub={`${monthReport?.count ?? 0} registros`}
          />
          <KpiCard
            label="Promedio por transacción"
            value={
              monthReport && monthReport.count > 0
                ? formatCLP(monthReport.total / monthReport.count)
                : '$0'
            }
          />
          <KpiCard
            label="Promedio mensual"
            value={trendData ? formatCLP(trendData.average_monthly) : '$0'}
            sub={`Últimos ${trendData?.months ?? 6} meses`}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <h2 className="text-sm font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>
              Tendencia mensual
            </h2>
            {trendData && trendData.trend.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={trendData.trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                  <XAxis dataKey="month" stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} />
                  <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} tickFormatter={tickCLP} />
                  <Tooltip
                    formatter={(v: number) => [formatCLP(v), 'Total']}
                    contentStyle={{ backgroundColor: 'var(--bg-card-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="total"
                    name="Total"
                    stroke={CHART_COLORS.line}
                    strokeWidth={2}
                    dot={{ fill: CHART_COLORS.line, r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>Sin datos disponibles</p>
            )}
          </div>

          <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <h2 className="text-sm font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>
              Distribución por categoría
            </h2>
            {categoryData && categoryData.categories.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={categoryData.categories}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                  <XAxis dataKey="category" stroke={CHART_COLORS.axis} tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                  <YAxis stroke={CHART_COLORS.axis} tick={{ fontSize: 11 }} tickFormatter={tickCLP} />
                  <Tooltip
                    formatter={(v: number) => [formatCLP(v), 'Total']}
                    contentStyle={{ backgroundColor: 'var(--bg-card-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Bar dataKey="total" name="Total" fill={CHART_COLORS.bar} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>Sin datos disponibles</p>
            )}
          </div>
        </div>

        {/* Desglose del mes */}
        {balance && balance.by_category.length > 0 && (
          <div className="rounded-xl border overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
              <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                Desglose del mes
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-card-2)' }}>
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Categoría</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Tipo</th>
                    <th className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Registros</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {balance.by_category.map((row, idx) => (
                    <tr
                      key={idx}
                      className="border-t transition-colors"
                      style={{ borderColor: 'var(--border)' }}
                    >
                      <td className="px-5 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {row.category}
                      </td>
                      <td className="px-5 py-3 text-sm">
                        <span
                          className="px-2 py-0.5 rounded-full text-xs font-semibold"
                          style={{
                            backgroundColor: row.type === 'income' ? 'rgba(93,202,165,0.15)' : 'rgba(232,93,36,0.15)',
                            color: row.type === 'income' ? '#5DCAA5' : '#E85D24',
                          }}
                        >
                          {row.type === 'income' ? 'ingreso' : 'gasto'}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-sm text-center tabular-nums" style={{ color: 'var(--text-muted)' }}>
                        {row.count}
                      </td>
                      <td
                        className="px-5 py-3 text-sm font-semibold text-right tabular-nums"
                        style={{ color: row.type === 'income' ? '#5DCAA5' : 'var(--text-primary)' }}
                      >
                        {formatCLP(row.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Top comercios */}
        <div className="rounded-xl border overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Top comercios
            </h2>
          </div>
          {topMerchants.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-card-2)' }}>
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Comercio</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Transacciones</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {topMerchants.map((m, idx) => (
                    <tr key={idx} className="border-t" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-5 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {m.merchant || 'Desconocido'}
                      </td>
                      <td className="px-5 py-3 text-sm tabular-nums" style={{ color: 'var(--text-muted)' }}>
                        {m.count}
                      </td>
                      <td className="px-5 py-3 text-sm font-semibold text-right tabular-nums" style={{ color: 'var(--text-primary)' }}>
                        {formatCLP(m.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-center py-10 text-sm" style={{ color: 'var(--text-muted)' }}>
              Sin comercios registrados
            </p>
          )}
        </div>
      </div>
    </>
  );
}

