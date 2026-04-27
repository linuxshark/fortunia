# Fortunia v2 — Design Spec
**Date:** 2026-04-27  
**Status:** Approved  
**Author:** Raúl Linares + Claude

## Overview

Extend Fortunia with four capabilities:
1. **Income tracking** — register income ("recibí 4.000.000 de sueldo") alongside expenses
2. **Month-by-month view** — dashboard with month navigator and per-month income/expense/balance breakdown
3. **Expanded categories** — richer category set with explicit income vs. expense categories
4. **Multi-user identity** — map Telegram IDs to named users; filter dashboard by user; family-consolidated view as default

Current users: Raúl Linares (Telegram ID: 757348065). Wife to be added later as a second INSERT.

---

## Section 1: Database

### New table: `users`

```sql
CREATE TABLE users (
    id           SERIAL PRIMARY KEY,
    telegram_id  BIGINT UNIQUE NOT NULL,
    display_name VARCHAR(50) NOT NULL,
    user_key     VARCHAR(50) UNIQUE NOT NULL,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO users (telegram_id, display_name, user_key)
VALUES (757348065, 'Raúl Linares', 'raul');
```

`user_key` is the internal stable identifier used in `expenses.user_id` and API responses (e.g. `"raul"`). `display_name` is for UI display only.

### Migration: `expenses` table

```sql
ALTER TABLE expenses
    ADD COLUMN type VARCHAR(10) NOT NULL DEFAULT 'expense'
        CHECK (type IN ('expense', 'income'));
```

No change to `amount > 0` constraint — income amounts are also positive.

Existing rows keep `type='expense'` via the DEFAULT.

### Migration: `categories` table

```sql
ALTER TABLE categories
    ADD COLUMN applicable_to VARCHAR(10) NOT NULL DEFAULT 'expense'
        CHECK (applicable_to IN ('expense', 'income', 'both'));
```

### Category seed — replace all 7 with 11

| Name | applicable_to | Keywords (sample) |
|---|---|---|
| Sueldo | income | sueldo, salario, remuneración |
| Otros Ingresos | income | freelance, pago, transferencia, ingreso |
| Comida | expense | supermercado, jumbo, lider, unimarc, tottus, almacén, feria |
| Restaurantes | expense | restaurant, restaurante, sushi, pizza, café, cafe, almuerzo, cena |
| Transporte | expense | uber, didi, cabify, taxi, metro, bip |
| Combustible | expense | bencina, combustible, copec, shell, enex, petróleo |
| Entretenimiento | expense | netflix, spotify, disney, cine, steam, juegos, teatro |
| Salud | expense | farmacia, salcobrand, cruz verde, médico, clínica, dental |
| Hogar | expense | arriendo, dividendo, luz, enel, agua, gas, internet, condominio |
| Ropa | expense | ropa, zapatos, zapatillas, h&m, zara, falabella |
| Otros | both | (catch-all, empty keywords) |

### Materialized view: `monthly_summaries` — rebuild

```sql
DROP MATERIALIZED VIEW monthly_summaries;

CREATE MATERIALIZED VIEW monthly_summaries AS
SELECT
    user_id,
    date_trunc('month', spent_at) AS month,
    type,
    category_id,
    COUNT(*)       AS count,
    SUM(amount)    AS total,
    AVG(amount)    AS avg
FROM expenses
GROUP BY user_id, date_trunc('month', spent_at), type, category_id;

CREATE UNIQUE INDEX ON monthly_summaries(user_id, month, type, category_id);
```

---

## Section 2: Parser and API

### `ParsedExpense` dataclass change

Add `type: str = "expense"` field.

```python
@dataclass
class ParsedExpense:
    amount: Optional[Decimal] = None
    currency: str = "CLP"
    type: str = "expense"           # NEW
    category_hint: Optional[str] = None
    merchant_hint: Optional[str] = None
    note: Optional[str] = None
    confidence: float = 0.0
    parse_method: str = "rules"
```

### Income verb detection in `text_parser.py`

Before amount extraction, check for income verbs:

```python
INCOME_VERBS = [
    "recibí", "recibi", "cobré", "cobre", "me pagaron", "me depositaron",
    "me transfirieron", "llegó el sueldo", "cayó el sueldo", "cayo el sueldo",
    "me entraron", "gané", "gane", "me llegó", "me llego",
]

def _is_income(text: str) -> bool:
    text_lower = text.lower()
    return any(v in text_lower for v in INCOME_VERBS)
```

If `_is_income(text)` is True → `result.type = "income"`, and category_hint lookup restricts to `applicable_to IN ('income', 'both')`.

### `intent_detector` additions

Add income phrases to the positive finance patterns so messages like "recibí mi sueldo" are detected as financial.

### User resolution in API

New Alembic migration adds `users` table. New dependency:

```python
async def resolve_user(telegram_id: int, db: Session) -> User:
    user = db.query(User).filter_by(telegram_id=telegram_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=403, detail="Telegram user not authorized")
    return user
```

### Request schema change: `IngestTextRequest`

```python
class IngestTextRequest(BaseModel):
    text: str
    telegram_id: Optional[int] = None   # NEW — preferred
    user_id: Optional[str] = "user"     # LEGACY — kept for backwards compat with existing Kraken integration
    msg_id: Optional[str] = None
```

Resolution order: if `telegram_id` provided → resolve to `user_key` via DB. If not → fallback to `user_id` string (legacy). This allows the existing Kraken integration to keep working while the new identity system is wired up.

### New endpoint: `GET /reports/monthly-balance`

```
GET /reports/monthly-balance?user_id=raul&month=2026-04
GET /reports/monthly-balance?user_id=all&month=2026-04
```

Response:
```json
{
  "month": "2026-04",
  "user_id": "raul",
  "total_income": 4000000,
  "total_expenses": 850000,
  "balance": 3150000,
  "by_category": [
    {"category": "Sueldo", "type": "income", "total": 4000000, "count": 1},
    {"category": "Comida", "type": "expense", "total": 120000, "count": 8}
  ]
}
```

When `user_id=all`, sums across all active users. The `by_category` array still shows per-category detail.

### Existing endpoints: `ingest/text`

The router saves `expense.type` from `parsed.type`. No other changes to the happy path.

---

## Section 3: Dashboard

### New components

| Component | Purpose |
|---|---|
| `MonthNavigator` | `← Abril 2026 →` — controls active month state passed to all fetch calls |
| `UserFilter` | Dropdown: Todos / Raúl / [display_name of wife] — fetched from `GET /reports/users` |
| `BalanceCard` | Three-card row: Ingresos (green) / Gastos (coral) / Balance (green or red) |
| `TransactionTable` | Modified: adds `Tipo` (ingreso/gasto badge) and `Usuario` columns |

### Modified: `page.tsx`

- Replaces hardcoded `DEFAULT_USER = 'user'` with state from `UserFilter`
- Replaces hardcoded current month with state from `MonthNavigator`
- Adds `BalanceCard` above the charts
- All `fetchXxx` calls pass `{ userId, month }` from state

### New: `lib/api-client.ts` additions

```typescript
fetchMonthlyBalance(userId: string, month: string): Promise<MonthlyBalance>
fetchUsers(): Promise<User[]>   // for UserFilter population
```

### New endpoint for dashboard: `GET /reports/users`

Returns active users for the filter dropdown:
```json
[
  {"user_key": "all", "display_name": "Todos"},
  {"user_key": "raul", "display_name": "Raúl Linares"}
]
```

### Visual conventions

- Income values: `#5DCAA5` (green)
- Expense values: `#E85D24` (coral/red)
- Balance positive: `#5DCAA5`; negative: `#E85D24`
- Badge "ingreso" → green pill; "gasto" → coral pill

---

## Out of Scope (v2)

- Budget limits / alerts per category
- Export to CSV/Excel
- Push notifications for overspending
- Currency other than CLP
- Third user support (will be a single INSERT when needed)

---

## Implementation Order

1. **DB migration** — `users` table, `expenses.type` column, `categories.applicable_to`, rebuild `monthly_summaries` view, re-seed categories
2. **Parser** — income verb detection, `ParsedExpense.type` field, category filter by `applicable_to`
3. **API** — `resolve_user` dependency, `IngestTextRequest` schema, `ingest/text` router update, new `monthly-balance` and `users` endpoints
4. **Dashboard** — `MonthNavigator`, `UserFilter`, `BalanceCard`, `TransactionTable` updates, `api-client.ts` additions
5. **Tests** — intent detector income cases, parser income cases, API endpoint tests, migration smoke test
