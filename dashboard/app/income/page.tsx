'use client';

import TransactionsList from '@/app/components/TransactionsList';

export default function IncomePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
        Ingresos
      </h1>
      <TransactionsList type="income" />
    </div>
  );
}
