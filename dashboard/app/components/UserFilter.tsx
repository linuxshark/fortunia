'use client';

import { useEffect, useState } from 'react';
import { fetchUsers, UserItem } from '@/lib/api-client';

interface Props {
  value: string;
  onChange: (userKey: string) => void;
}

export default function UserFilter({ value, onChange }: Props) {
  const [users, setUsers] = useState<UserItem[]>([]);

  useEffect(() => {
    fetchUsers().then(setUsers).catch(() => {
      setUsers([{ user_key: 'all', display_name: 'Todos' }]);
    });
  }, []);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2"
      style={{
        backgroundColor: 'var(--bg-card)',
        color: 'var(--text-primary)',
        border: '1px solid var(--border)',
      }}
    >
      {users.map((u) => (
        <option key={u.user_key} value={u.user_key}>
          {u.display_name}
        </option>
      ))}
    </select>
  );
}
