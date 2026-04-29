'use client';

import { useEffect, useState } from 'react';
import { fetchExpenses, deleteExpense, Expense } from '@/lib/api-client';
import EditExpenseModal from './EditExpenseModal';
import { format, parseISO } from 'date-fns';

interface Props {
  type: 'expense' | 'income';
}

const LIMIT = 50;

const formatCLP = (amount: number) => {
  const abs = Math.abs(Math.round(amount));
  const formatted = abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return amount < 0 ? `-$${formatted}` : `$${formatted}`;
};

export default function TransactionsList({ type }: Props) {
  const userId = 'all';
  const [records, setRecords] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<Expense | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchExpenses(userId, LIMIT, offset, undefined, undefined, undefined, type)
      .then(setRecords)
      .catch(() => setError(`Error al cargar los ${type === 'income' ? 'ingresos' : 'gastos'}`))
      .finally(() => setLoading(false));
  }, [type, offset]);

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este registro?')) return;
    try {
      await deleteExpense(id);
      setRecords((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError('Error al eliminar el registro');
    }
  };

  const handleSaved = (updated: Expense) => {
    setRecords((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    setEditing(null);
  };

  const isIncome = type === 'income';
  const amountColor = isIncome ? '#5DCAA5' : 'var(--text-primary)';

  if (loading) {
    return (
      <div className="flex flex-col gap-3 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-12 rounded-xl" style={{ backgroundColor: 'var(--bg-card)' }} />
        ))}
      </div>
    );
  }

  return (
    <>
      {editing && (
        <EditExpenseModal
          expense={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}

      {error && (
        <div
          className="rounded-xl p-4 text-sm mb-4"
          style={{ backgroundColor: '#2d1a1a', color: '#E85D24', border: '1px solid #6b2a1a' }}
        >
          {error}
        </div>
      )}

      <div className="rounded-xl border overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        {records.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-card-2)' }}>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Fecha</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Comercio</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Categoría</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Nota</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Monto</th>
                  <th className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Confianza</th>
                  <th className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id} className="border-t" style={{ borderColor: 'var(--border)' }}>
                    <td className="px-5 py-3 text-sm" style={{ color: 'var(--text-muted)' }}>
                      {format(parseISO(r.spent_at), 'dd/MM/yyyy HH:mm')}
                    </td>
                    <td className="px-5 py-3 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {r.merchant_name || '—'}
                    </td>
                    <td className="px-5 py-3 text-sm">
                      <span
                        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                        style={{
                          backgroundColor: isIncome ? 'rgba(93,202,165,0.15)' : 'rgba(59,110,248,0.15)',
                          color: isIncome ? '#5DCAA5' : '#3b6ef8',
                        }}
                      >
                        {r.category_name || 'Otros'}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-sm" style={{ color: 'var(--text-muted)' }}>
                      {r.note || '—'}
                    </td>
                    <td className="px-5 py-3 text-sm text-right font-semibold tabular-nums" style={{ color: amountColor }}>
                      {formatCLP(r.amount)}
                    </td>
                    <td className="px-5 py-3 text-sm text-center">
                      {r.confidence != null ? (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor:
                              r.confidence > 0.8
                                ? 'rgba(93,202,165,0.15)'
                                : r.confidence > 0.6
                                ? 'rgba(245,158,11,0.15)'
                                : 'rgba(232,93,36,0.15)',
                            color:
                              r.confidence > 0.8
                                ? '#5DCAA5'
                                : r.confidence > 0.6
                                ? '#F59E0B'
                                : '#E85D24',
                          }}
                        >
                          {Math.round(r.confidence * 100)}%
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-sm text-center">
                      <div className="flex items-center justify-center gap-3">
                        <button
                          onClick={() => setEditing(r)}
                          className="font-medium"
                          style={{ color: '#3b6ef8' }}
                        >
                          Editar
                        </button>
                        <span style={{ color: 'var(--border)' }}>|</span>
                        <button
                          onClick={() => handleDelete(r.id)}
                          className="font-medium"
                          style={{ color: '#E85D24' }}
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              No hay {isIncome ? 'ingresos' : 'gastos'} registrados.
            </p>
          </div>
        )}
      </div>

      {/* Paginación */}
      <div className="flex items-center justify-between mt-4">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Mostrando {records.length} {isIncome ? 'ingresos' : 'gastos'}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - LIMIT))}
            disabled={offset === 0}
            className="px-4 py-2 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-muted)',
              borderColor: 'var(--border)',
            }}
          >
            Anterior
          </button>
          <button
            onClick={() => setOffset(offset + LIMIT)}
            disabled={records.length < LIMIT}
            className="px-4 py-2 rounded-lg text-sm font-medium border transition-colors disabled:opacity-40"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-muted)',
              borderColor: 'var(--border)',
            }}
          >
            Siguiente
          </button>
        </div>
      </div>
    </>
  );
}
