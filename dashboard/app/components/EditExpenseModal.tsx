'use client';

import { useState, useEffect } from 'react';
import { updateExpense, fetchCategories, Expense, Category } from '@/lib/api-client';
import { format, parseISO } from 'date-fns';

interface Props {
  expense: Expense;
  onClose: () => void;
  onSaved: (updated: Expense) => void;
}

const labelCls = 'block text-xs font-semibold uppercase tracking-wider mb-1.5';
const inputCls =
  'w-full rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';
const inputStyle = {
  backgroundColor: 'var(--bg-card-2)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border)',
};

export default function EditExpenseModal({ expense, onClose, onSaved }: Props) {
  const [amount, setAmount] = useState(String(expense.amount));
  const [type, setType] = useState<'expense' | 'income'>(
    (expense as any).type ?? 'expense'
  );
  const [categoryId, setCategoryId] = useState<string>(
    expense.category_id != null ? String(expense.category_id) : ''
  );
  const [merchantName, setMerchantName] = useState(expense.merchant_name ?? '');
  const [note, setNote] = useState(expense.note ?? '');
  const [spentAt, setSpentAt] = useState(
    format(parseISO(expense.spent_at), "yyyy-MM-dd'T'HH:mm")
  );
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseFloat(amount);
    if (isNaN(parsed) || parsed <= 0) {
      setError('El monto debe ser un número mayor a 0');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const updated = await updateExpense(expense.id, {
        amount: parsed,
        type,
        category_id: categoryId !== '' ? Number(categoryId) : null,
        merchant_name: merchantName,
        note,
        spent_at: new Date(spentAt).toISOString(),
      });
      onSaved(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al guardar los cambios');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}
    >
      <div
        className="w-full max-w-lg rounded-2xl shadow-2xl p-6"
        style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
            Editar gasto #{expense.id}
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-sm"
            style={{ color: 'var(--text-muted)', backgroundColor: 'var(--bg-card-2)' }}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Fecha */}
          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>Fecha y hora</label>
            <input
              type="datetime-local"
              required
              value={spentAt}
              onChange={(e) => setSpentAt(e.target.value)}
              className={inputCls}
              style={inputStyle}
            />
          </div>

          {/* Monto + Tipo */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls} style={{ color: 'var(--text-muted)' }}>Monto</label>
              <input
                type="number"
                required
                min="1"
                step="1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className={inputCls}
                style={inputStyle}
              />
            </div>
            <div>
              <label className={labelCls} style={{ color: 'var(--text-muted)' }}>Tipo</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as 'expense' | 'income')}
                className={inputCls}
                style={inputStyle}
              >
                <option value="expense">Gasto</option>
                <option value="income">Ingreso</option>
              </select>
            </div>
          </div>

          {/* Categoría */}
          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>Categoría</label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className={inputCls}
              style={inputStyle}
            >
              <option value="">— Sin categoría —</option>
              {categories.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Comercio */}
          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>Comercio</label>
            <input
              type="text"
              value={merchantName}
              onChange={(e) => setMerchantName(e.target.value)}
              placeholder="Ej: Jumbo, Netflix..."
              className={inputCls}
              style={inputStyle}
            />
          </div>

          {/* Nota */}
          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>Nota</label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Descripción del gasto..."
              className={inputCls}
              style={inputStyle}
            />
          </div>

          {error && (
            <p
              className="text-sm rounded-lg px-3 py-2"
              style={{ backgroundColor: '#2d1a1a', color: '#E85D24' }}
            >
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-lg py-2 text-sm font-medium"
              style={{
                backgroundColor: 'var(--bg-card-2)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 rounded-lg py-2 text-sm font-bold disabled:opacity-50"
              style={{ backgroundColor: '#3b6ef8', color: '#fff' }}
            >
              {loading ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
