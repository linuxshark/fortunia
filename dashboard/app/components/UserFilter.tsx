'use client';

import { useEffect, useState } from 'react';
import { fetchUsers, UserItem } from '@/lib/api-client';

interface Props {
  value: string;        // user_key or "all"
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
      className="border border-gray-300 rounded-md px-3 py-1.5 text-sm text-gray-700 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {users.map((u) => (
        <option key={u.user_key} value={u.user_key}>
          {u.display_name}
        </option>
      ))}
    </select>
  );
}
