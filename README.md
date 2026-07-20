# an5Adapters

Standalone runtime adapters for AN5 ORM. Provides connection pooling, query execution, and typed table clients in TypeScript, Python, and .NET.

## Features

- **Connection pooling** — Managed connection pools with configurable limits
- **Type-safe table clients** — Generic CRUD operations with type inference
- **Full query support** — WHERE, ORDER BY, pagination, aggregates
- **Vector search** — Cosine, euclidean, and dot product similarity
- **Transactions** — Begin/commit/rollback with automatic cleanup
- **Cross-language** — Same API in TypeScript, Python, and .NET

## Installation

### TypeScript

```bash
npm install an5-adapters
```

### Python

```bash
pip install an5-adapters
```

### .NET

```bash
dotnet add package An5Adapters
```

## Usage

### TypeScript

```typescript
import { createAn5Adapter } from 'an5-adapters';

const db = createAn5Adapter({
  connectionString: 'sqlserver://localhost:1433;database=mydb;user=sa;password=pass',
});

// Table client
const users = db.table<User>('users');
await users.findMany({ where: { active: true }, take: 10 });

// Raw queries
const rows = await db.exec('SELECT * FROM users WHERE id = @id', { id: '123' });

// Transactions
await db.$transaction(async (tx) => {
  await tx.table('users').create({ data: { name: 'John' } });
});
```

### Python

```python
from an5_adapter import create_an5_adapter

db = create_an5_adapter("sqlserver://localhost:1433;database=mydb;user=sa;password=pass")

# Table client
users = db.table("User")
users.find_many(where={"active": True}, take=10)

# Raw queries
rows = db.exec("SELECT * FROM users WHERE id = ?", params=["123"])

# Transactions
db.transaction(lambda tx: tx.table("User").create({"name": "John"}))
```

### .NET

```csharp
using An5Orm;

var db = new An5Adapter(connectionString);

// Table client
var users = db.Table<User>("dbo.users");
var activeUsers = users.FindMany("IsActive = @p", new { p = true });

// Raw queries
var rows = db.QueryRaw("SELECT * FROM users WHERE Id = @id", new { id = "123" });

// Transactions
db.Transaction(tx => {
    tx.Table<User>("dbo.users").Create(new User { Name = "John" });
});
```

## API Reference

### An5Adapter

| Method | Description |
|--------|-------------|
| `exec(query, params)` | Execute query, return rows |
| `table<T>(name)` | Get typed table client |
| `$transaction(fn)` | Execute in transaction |
| `$connect()` | Open connection pool |
| `$disconnect()` | Close connection pool |

### AdapterTableClient

| Method | Description |
|--------|-------------|
| `findMany(args)` | Query multiple rows |
| `findFirst(args)` | Query single row |
| `findUnique(where)` | Find by unique key |
| `count(where)` | Count rows |
| `create(data)` | Insert row |
| `createMany(data)` | Bulk insert |
| `update(where, data)` | Update row |
| `updateMany(where, data)` | Update multiple rows |
| `delete(where)` | Delete row |
| `deleteMany(where)` | Delete multiple rows |
| `upsert(where, create, update)` | Insert or update |
| `aggregate(args)` | SUM, AVG, MIN, MAX, COUNT |
| `groupBy(args)` | Group by fields |
| `vectorSearch(args)` | Semantic similarity search |

## Testing

```bash
# TypeScript/Node
node test/unit.test.js

# Python
python -m compileall python
python test/smoke.py
```

## License

MIT
