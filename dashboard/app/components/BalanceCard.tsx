interface Props {
  totalIncome: number;
  totalExpenses: number;
  balance: number;
}

const formatCLP = (v: number) => {
  const abs = Math.abs(Math.round(v));
  const formatted = abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return v < 0 ? `-$${formatted}` : `$${formatted}`;
};

export default function BalanceCard({ totalIncome, totalExpenses, balance }: Props) {
  const positive = balance >= 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#5DCAA5' }} />
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Ingresos del mes
          </p>
        </div>
        <p className="text-3xl font-bold tabular-nums" style={{ color: '#5DCAA5' }}>
          {formatCLP(totalIncome)}
        </p>
      </div>

      <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#E85D24' }} />
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Gastos del mes
          </p>
        </div>
        <p className="text-3xl font-bold tabular-nums" style={{ color: '#E85D24' }}>
          {formatCLP(totalExpenses)}
        </p>
      </div>

      <div className="rounded-xl p-5 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: positive ? '#5DCAA5' : '#E85D24' }} />
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Balance neto
          </p>
        </div>
        <p className="text-3xl font-bold tabular-nums" style={{ color: positive ? '#5DCAA5' : '#E85D24' }}>
          {formatCLP(balance)}
        </p>
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          {positive ? '↑ superávit' : '↓ déficit'}
        </p>
      </div>
    </div>
  );
}
