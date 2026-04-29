'use client';

import { useEffect, useState } from 'react';
import {
  PieChart, Pie, Cell, Tooltip,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { fetchCategoryReport, fetchCategories, deleteCategory, CategorySummary, Category } from '@/lib/api-client';
import NewCategoryModal from '@/app/components/NewCategoryModal';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

const TYPE_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  expense: { bg: 'rgba(232,93,36,0.15)', color: '#E85D24', label: 'gasto' },
  income:  { bg: 'rgba(93,202,165,0.15)', color: '#5DCAA5', label: 'ingreso' },
  both:    { bg: 'rgba(59,110,248,0.15)', color: '#3b6ef8', label: 'ambos' },
};

const DEFAULT_USER = 'user';

const formatCLP = (v: number) => {
  const abs = Math.abs(Math.round(v));
  const formatted = abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return v < 0 ? `-$${formatted}` : `$${formatted}`;
};

export default function Categories() {
  const [userId] = useState(DEFAULT_USER);
  const [allCategories, setAllCategories] = useState<Category[]>([]);
  const [reportCategories, setReportCategories] = useState<CategorySummary[]>([]);
  const [grandTotal, setGrandTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNewCategory, setShowNewCategory] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadAll = async () => {
    try {
      setLoading(true);
      const [all, report] = await Promise.all([
        fetchCategories(),
        fetchCategoryReport(userId).catch(() => ({ categories: [], total: 0, period: 'month' })),
      ]);
      setAllCategories(all);
      setReportCategories(report.categories);
      setGrandTotal(report.total);
    } catch (err) {
      setError('Error al cargar las categorías');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (cat: Category) => {
    if (!confirm(`¿Eliminar la categoría "${cat.name}"? Esta acción no se puede deshacer.`)) return;
    setDeletingId(cat.id);
    setDeleteError(null);
    try {
      await deleteCategory(cat.id);
      await loadAll();
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Error al eliminar la categoría';
      setDeleteError(msg);
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => { loadAll(); }, [userId]);

  if (loading) {
    return (
      <div className="flex flex-col gap-4 animate-pulse">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="h-16 rounded-xl" style={{ backgroundColor: 'var(--bg-card)' }} />
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
    <div className="space-y-6">
      {showNewCategory && (
        <NewCategoryModal
          onClose={() => setShowNewCategory(false)}
          onCreated={() => { setShowNewCategory(false); loadAll(); }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Categorías</h1>
        <button
          onClick={() => setShowNewCategory(true)}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
          style={{ backgroundColor: '#3b6ef8', color: '#fff' }}
        >
          <span>+</span>
          <span>Nueva categoría</span>
        </button>
      </div>

      {/* Chips de todas las categorías definidas */}
      <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
          Categorías definidas ({allCategories.length})
        </p>
        {deleteError && (
          <div className="mb-3 rounded-lg px-3 py-2 text-xs font-medium" style={{ backgroundColor: 'rgba(232,93,36,0.12)', color: '#E85D24', border: '1px solid rgba(232,93,36,0.3)' }}>
            {deleteError}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {allCategories.map((cat) => {
            const style = TYPE_STYLE[cat.applicable_to] ?? TYPE_STYLE.both;
            const isDeleting = deletingId === cat.id;
            return (
              <span
                key={cat.id}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium border"
                style={{
                  backgroundColor: cat.color ? `${cat.color}22` : style.bg,
                  color: cat.color ?? style.color,
                  borderColor: cat.color ?? style.color,
                  opacity: isDeleting ? 0.5 : 1,
                }}
              >
                {cat.name}
                <span
                  className="text-xs rounded-full px-1.5 py-0.5 font-semibold"
                  style={{ backgroundColor: style.bg, color: style.color }}
                >
                  {style.label}
                </span>
                <button
                  onClick={() => handleDelete(cat)}
                  disabled={isDeleting}
                  title="Eliminar categoría"
                  className="ml-0.5 rounded-full w-4 h-4 flex items-center justify-center transition-opacity hover:opacity-70"
                  style={{ color: cat.color ?? style.color }}
                >
                  {isDeleting ? '…' : '×'}
                </button>
              </span>
            );
          })}
          {allCategories.length === 0 && (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No hay categorías aún.</p>
          )}
        </div>
      </div>

      {/* Gráficos y tabla — solo si hay datos de gasto */}
      {reportCategories.length > 0 && (
        <>
          <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-muted)' }}>
              Gasto total del período
            </p>
            <p className="text-3xl font-bold tabular-nums mb-5" style={{ color: 'var(--text-primary)' }}>
              {formatCLP(grandTotal)}
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>Distribución</p>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={reportCategories}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ category, percentage }) => `${category} (${percentage.toFixed(1)}%)`}
                      outerRadius={90}
                      dataKey="total"
                    >
                      {reportCategories.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => formatCLP(value)}
                      contentStyle={{ backgroundColor: 'var(--bg-card-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: 'var(--text-primary)' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>Monto por categoría</p>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={reportCategories}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="category" stroke="var(--text-muted)" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" height={70} />
                    <YAxis stroke="var(--text-muted)" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip
                      formatter={(value: number) => formatCLP(value)}
                      contentStyle={{ backgroundColor: 'var(--bg-card-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: 'var(--text-primary)' }}
                    />
                    <Bar dataKey="total" name="Total" fill="#3b6ef8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="rounded-xl border overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
            <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
              <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Desglose</p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr style={{ backgroundColor: 'var(--bg-card-2)' }}>
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Categoría</th>
                    <th className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Transacciones</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Total</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>%</th>
                  </tr>
                </thead>
                <tbody>
                  {reportCategories.map((cat, idx) => (
                    <tr key={idx} className="border-t" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-5 py-3 text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                          <span style={{ color: 'var(--text-primary)' }}>{cat.category}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-sm text-center tabular-nums" style={{ color: 'var(--text-muted)' }}>{cat.count}</td>
                      <td className="px-5 py-3 text-sm text-right font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>{formatCLP(cat.total)}</td>
                      <td className="px-5 py-3 text-sm text-right tabular-nums" style={{ color: 'var(--text-muted)' }}>{cat.percentage.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {reportCategories.length === 0 && (
        <div className="rounded-xl p-8 text-center border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Aún no hay gastos registrados en este período.
          </p>
        </div>
      )}
    </div>
  );
}
