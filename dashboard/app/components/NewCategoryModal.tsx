'use client';

import { useState } from 'react';
import { createCategory } from '@/lib/api-client';

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function NewCategoryModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState('');
  const [applicableTo, setApplicableTo] = useState<'expense' | 'income' | 'both'>('expense');
  const [keywords, setKeywords] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      await createCategory({
        name: name.trim(),
        applicable_to: applicableTo,
        keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
      });
      onCreated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al crear la categoría');
    } finally {
      setLoading(false);
    }
  };

  const labelCls = "block text-xs font-semibold uppercase tracking-wider mb-1.5";
  const inputCls = "w-full rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}>
      <div className="w-full max-w-md rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
            Nueva categoría
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-sm transition-colors"
            style={{ color: 'var(--text-muted)', backgroundColor: 'var(--bg-card-2)' }}
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>
              Nombre
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Mascotas"
              className={inputCls}
              style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            />
          </div>

          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>
              Aplica a
            </label>
            <select
              value={applicableTo}
              onChange={(e) => setApplicableTo(e.target.value as 'expense' | 'income' | 'both')}
              className={inputCls}
              style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            >
              <option value="expense">Gastos</option>
              <option value="income">Ingresos</option>
              <option value="both">Ambos</option>
            </select>
          </div>

          <div>
            <label className={labelCls} style={{ color: 'var(--text-muted)' }}>
              Palabras clave{' '}
              <span className="normal-case font-normal" style={{ color: 'var(--text-muted)' }}>
                (separadas por coma)
              </span>
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Ej: veterinaria, petco, mascotas"
              className={inputCls}
              style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
            />
          </div>

          {error && (
            <p className="text-sm rounded-lg px-3 py-2" style={{ backgroundColor: '#2d1a1a', color: '#E85D24' }}>
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-lg py-2 text-sm font-medium transition-colors"
              style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex-1 rounded-lg py-2 text-sm font-bold transition-colors disabled:opacity-50"
              style={{ backgroundColor: '#3b6ef8', color: '#fff' }}
            >
              {loading ? 'Creando…' : 'Crear categoría'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
