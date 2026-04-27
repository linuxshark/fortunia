'use client';

import { format, addMonths, subMonths, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';

interface Props {
  value: string;       // "YYYY-MM"
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
    <div className="flex items-center gap-3">
      <button
        onClick={prev}
        className="p-1 rounded hover:bg-gray-100 text-gray-600 font-bold text-lg"
        aria-label="Mes anterior"
      >
        ←
      </button>
      <span className="text-base font-semibold text-gray-800 capitalize min-w-[140px] text-center">
        {label}
      </span>
      <button
        onClick={next}
        disabled={isCurrentMonth}
        className="p-1 rounded hover:bg-gray-100 text-gray-600 font-bold text-lg disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label="Mes siguiente"
      >
        →
      </button>
    </div>
  );
}
