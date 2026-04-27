interface Props {
  totalIncome: number;
  totalExpenses: number;
  balance: number;
}

function formatCLP(v: number) {
  return v.toLocaleString('es-CL', {
    style: 'currency',
    currency: 'CLP',
    minimumFractionDigits: 0,
  });
}

export default function BalanceCard({ totalIncome, totalExpenses, balance }: Props) {
  const balancePositive = balance >= 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-white rounded-lg shadow p-5 border-l-4 border-emerald-500">
        <p className="text-sm font-medium text-gray-500">Ingresos del mes</p>
        <p className="text-2xl font-bold text-emerald-600 mt-1">{formatCLP(totalIncome)}</p>
      </div>
      <div className="bg-white rounded-lg shadow p-5 border-l-4 border-orange-500">
        <p className="text-sm font-medium text-gray-500">Gastos del mes</p>
        <p className="text-2xl font-bold text-orange-600 mt-1">{formatCLP(totalExpenses)}</p>
      </div>
      <div className={`bg-white rounded-lg shadow p-5 border-l-4 ${balancePositive ? 'border-emerald-500' : 'border-red-500'}`}>
        <p className="text-sm font-medium text-gray-500">Balance neto</p>
        <p className={`text-2xl font-bold mt-1 ${balancePositive ? 'text-emerald-600' : 'text-red-600'}`}>
          {formatCLP(balance)}
        </p>
        <p className="text-xs text-gray-400 mt-1">{balancePositive ? '✅ positivo' : '⚠️ negativo'}</p>
      </div>
    </div>
  );
}
