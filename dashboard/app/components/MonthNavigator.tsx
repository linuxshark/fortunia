'use client';

import { format, addMonths, subMonths, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';

interface Props {
  value: string;
  onChange: (ym: string) => void;
}

export default function MonthNavigator({ value, onChange }: Props) {
  const current = parseISO(`${value}-01`);
  const prev = () => onChange(format(subMonths(current, 1), 'yyyy-MM'));
  const next = () => {
    const n = addMonths(current, 1);
    if (n <= new Date()) onChange(format(n, 'yyyy-MM'));
  };
  const label = format(current, 'MMMM yyyy', { locale: es });
  const isCurrentMonth = value === format(new Date(), 'yyyy-MM');

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={prev}
        className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors"
        style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
        aria-label="Mes anterior"
      >
        ←
      </button>
      <span
        className="text-sm font-semibold capitalize min-w-[140px] text-center"
        style={{ color: 'var(--text-primary)' }}
      >
        {label}
      </span>
      <button
        onClick={next}
        disabled={isCurrentMonth}
        className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
        aria-label="Mes siguiente"
      >
        →
      </button>
    </div>
  );
}
