"""
an5_adapter.py
Standalone Python runtime adapter for AN5 ORM.
Provides connection pooling, query execution and table client - works independently.

Usage:
    from an5Client.python.an5_adapter import create_an5_adapter
    db = create_an5_adapter(connection_string=os.environ["DATABASE_URL"])
    users = db.table("User").find_many(where={"is_active": True})
"""

import re
import uuid
import json
from typing import Any, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass

try:
    import pyodbc
    _BACKEND = "pyodbc"
except ImportError:
    pyodbc = None
    _BACKEND = None

import sys, os as _os
_client_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '../../an5Client/python')
if _client_dir not in sys.path:
    sys.path.insert(0, _client_dir)

try:
    from an5_metadata import MODEL_TO_TABLE, MODEL_FIELDS
    model_to_table = MODEL_TO_TABLE
    model_fields = MODEL_FIELDS
except ImportError:
    model_to_table: Dict[str, str] = {}
    model_fields: Dict[str, List[Dict]] = {}

T = TypeVar("T")

# ─── Connection ───────────────────────────────────────────────────────────────

def _parse_connection_string(url: str) -> str:
    """Convert sqlserver:// URL to pyodbc connection string."""
    url = url.replace("sqlserver://", "")
    parts = url.split(";")
    host_part = parts[0]
    host, _, port = host_part.partition(":")
    port = port or "1433"

    config: Dict[str, str] = {"server": host, "port": port}
    for part in parts[1:]:
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k = k.strip().lower()
        v = v.strip()
        if k in ("database",):
            config["database"] = v
        elif k in ("user", "uid"):
            config["user"] = v
        elif k in ("password", "pwd"):
            config["password"] = v
        elif k == "encrypt":
            config["encrypt"] = "yes" if v.lower() == "true" else "no"
        elif k == "trustservercertificate":
            config["trust"] = "yes" if v.lower() == "true" else "no"

    encrypt = config.get("encrypt", "yes")
    trust = config.get("trust", "yes")
    if "user" in config:
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config['server']},{config['port']};"
            f"DATABASE={config.get('database', '')};"
            f"UID={config['user']};"
            f"PWD={config.get('password', '')};"
            f"Encrypt={encrypt};TrustServerCertificate={trust};"
        )
    # Windows auth
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={config['server']},{config['port']};"
        f"DATABASE={config.get('database', '')};"
        f"Trusted_Connection=yes;"
        f"Encrypt={encrypt};TrustServerCertificate={trust};"
    )


# ─── Where clause builder ─────────────────────────────────────────────────────

def _parse_where(model_name: str, where: Optional[Dict], params: Dict, prefix: str = "") -> str:
    if not where:
        return ""
    conditions: List[str] = []

    for key, value in where.items():
        if key == "OR" and isinstance(value, list):
            sub = [_parse_where(model_name, v, params, f"{prefix}or{i}_") for i, v in enumerate(value)]
            sub = [s for s in sub if s]
            if sub:
                conditions.append(f"({' OR '.join(sub)})")
        elif key == "AND" and isinstance(value, list):
            sub = [_parse_where(model_name, v, params, f"{prefix}and{i}_") for i, v in enumerate(value)]
            sub = [s for s in sub if s]
            if sub:
                conditions.append(f"({' AND '.join(sub)})")
        else:
            col = f"[{key}]"
            pname = f"{prefix}{key}"
            if value is None:
                conditions.append(f"{col} IS NULL")
            elif isinstance(value, dict):
                if "not" in value:
                    if value["not"] is None:
                        conditions.append(f"{col} IS NOT NULL")
                    else:
                        p = f"{pname}_not"; params[p] = value["not"]
                        conditions.append(f"{col} <> ?")
                if "equals" in value:
                    params[f"{pname}_eq"] = value["equals"]
                    conditions.append(f"{col} = ?")
                if "contains" in value:
                    params[f"{pname}_co"] = f"%{value['contains']}%"
                    conditions.append(f"{col} LIKE ?")
                if "startsWith" in value:
                    params[f"{pname}_sw"] = f"{value['startsWith']}%"
                    conditions.append(f"{col} LIKE ?")
                if "endsWith" in value:
                    params[f"{pname}_ew"] = f"%{value['endsWith']}"
                    conditions.append(f"{col} LIKE ?")
                if "gte" in value:
                    params[f"{pname}_gte"] = value["gte"]
                    conditions.append(f"{col} >= ?")
                if "lte" in value:
                    params[f"{pname}_lte"] = value["lte"]
                    conditions.append(f"{col} <= ?")
                if "gt" in value:
                    params[f"{pname}_gt"] = value["gt"]
                    conditions.append(f"{col} > ?")
                if "lt" in value:
                    params[f"{pname}_lt"] = value["lt"]
                    conditions.append(f"{col} < ?")
                if "in" in value:
                    vals = value["in"]
                    if vals:
                        placeholders = ", ".join(["?"] * len(vals))
                        for v in vals:
                            params[f"{pname}_in"] = v
                        conditions.append(f"{col} IN ({placeholders})")
                    else:
                        conditions.append("1=0")
            else:
                params[pname] = value
                conditions.append(f"{col} = ?")

    return " AND ".join(conditions)


def _build_order_by(order_by: Any) -> str:
    if not order_by:
        return ""
    entries = order_by if isinstance(order_by, list) else [order_by]
    parts: List[str] = []
    for entry in entries:
        for col, direction in entry.items():
            parts.append(f"[{col}] {str(direction).upper()}")
    return f"ORDER BY {', '.join(parts)}" if parts else ""


# ─── Adapter ─────────────────────────────────────────────────────────────────

class An5Adapter:
    def __init__(self, connection_string: str):
        if not pyodbc:
            raise ImportError(
                "pyodbc is required: pip install pyodbc"
            )
        self._conn_str = _parse_connection_string(connection_string)

    def _connect(self):
        return pyodbc.connect(self._conn_str, autocommit=True)

    def exec(self, query: str, params: Optional[List] = None) -> List[Dict]:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            if cursor.description:
                cols = [col[0] for col in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]
            return []
        finally:
            conn.close()

    def execute(self, query: str, params: Optional[List] = None) -> int:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            return cursor.rowcount
        finally:
            conn.close()

    def query_raw(self, query: str, *values) -> List[Dict]:
        return self.exec(query, list(values))

    def execute_raw(self, query: str, *values) -> int:
        return self.execute(query, list(values))

    def table(self, model_name: str) -> "AdapterTableClient":
        return AdapterTableClient(self, model_name)

    def __getattr__(self, model_name: str) -> "AdapterTableClient":
        return self.table(model_name)

    def transaction(self, fn):
        conn = self._connect()
        conn.autocommit = False
        try:
            result = fn(self)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = True
            conn.close()


# ─── Table Client ─────────────────────────────────────────────────────────────

class AdapterTableClient:
    def __init__(self, adapter: An5Adapter, model_name: str):
        self._adapter = adapter
        self._model = model_name

    @property
    def _table(self) -> str:
        name = self._model
        if name in model_to_table:
            return model_to_table[name]
        camel = name[0].lower() + name[1:] if name else name
        if camel in model_to_table:
            return model_to_table[camel]
        lower = name.lower()
        if lower in model_to_table:
            return model_to_table[lower]
        return name

    @property
    def _table_sql(self) -> str:
        t = self._table
        if t.startswith('['):
            return t
        if '.' in t:
            return '.'.join(f"[{p}]" for p in t.split('.'))
        return f"[{t}]"

    def find_many(self, where=None, order_by=None, skip: int = 0, take: Optional[int] = None, select=None) -> List[Dict]:
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params)
        order_sql = _build_order_by(order_by)
        values = list(params.values())

        query = f"SELECT * FROM {self._table_sql} WITH (NOLOCK)"
        if where_sql:
            query += f" WHERE {where_sql}"
        if order_sql:
            query += f" {order_sql}"
        if take is not None:
            if not order_sql:
                query += " ORDER BY (SELECT NULL)"
            query += f" OFFSET {skip} ROWS FETCH NEXT {take} ROWS ONLY"
        return self._adapter.exec(query, values)

    def find_first(self, where=None, order_by=None, select=None) -> Optional[Dict]:
        rows = self.find_many(where=where, order_by=order_by, take=1, select=select)
        return rows[0] if rows else None

    def find_unique(self, where: Dict) -> Optional[Dict]:
        return self.find_first(where=where)

    def count(self, where=None) -> int:
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params)
        query = f"SELECT COUNT(*) AS cnt FROM {self._table_sql} WITH (NOLOCK)"
        if where_sql:
            query += f" WHERE {where_sql}"
        rows = self._adapter.exec(query, list(params.values()))
        return int(rows[0]["cnt"]) if rows else 0

    def create(self, data: Dict) -> Dict:
        fields = model_fields.get(self._model, [])
        id_field = next((f for f in fields if f.get("isId")), None)
        if id_field and id_field["name"] not in data:
            data = {**data, id_field["name"]: str(uuid.uuid4())}

        cols = [k for k, v in data.items() if v is not None]
        values = [data[c] for c in cols]
        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join(f"[{c}]" for c in cols)
        query = f"INSERT INTO {self._table_sql} ({col_list}) VALUES ({placeholders})"
        self._adapter.execute(query, values)

        if id_field:
            return self.find_first(where={id_field["name"]: data[id_field["name"]]}) or data
        return data

    def create_many(self, data: List[Dict], skip_duplicates: bool = False) -> Dict:
        count = 0
        for row in data:
            try:
                self.create(row)
                count += 1
            except Exception:
                if not skip_duplicates:
                    raise
        return {"count": count}

    def update(self, where: Dict, data: Dict) -> Optional[Dict]:
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params, "w_")
        set_parts: List[str] = []
        set_values: List = []
        for col, val in data.items():
            if val is not None:
                set_parts.append(f"[{col}] = ?")
                set_values.append(val)

        all_values = set_values + list(params.values())
        query = f"UPDATE {self._table_sql} SET {', '.join(set_parts)}"
        if where_sql:
            query += f" WHERE {where_sql}"
        self._adapter.execute(query, all_values)
        return self.find_first(where=where)

    def update_many(self, where: Optional[Dict], data: Dict) -> Dict:
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params, "w_")
        set_parts: List[str] = []
        set_values: List = []
        for col, val in data.items():
            set_parts.append(f"[{col}] = ?")
            set_values.append(val)
        all_values = set_values + list(params.values())
        query = f"UPDATE {self._table_sql} SET {', '.join(set_parts)}"
        if where_sql:
            query += f" WHERE {where_sql}"
        count = self._adapter.execute(query, all_values)
        return {"count": count}

    def delete(self, where: Dict) -> Optional[Dict]:
        existing = self.find_first(where=where)
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params)
        query = f"DELETE FROM {self._table_sql} WHERE {where_sql}"
        self._adapter.execute(query, list(params.values()))
        return existing

    def delete_many(self, where: Optional[Dict] = None) -> Dict:
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params)
        query = f"DELETE FROM {self._table_sql}"
        if where_sql:
            query += f" WHERE {where_sql}"
        count = self._adapter.execute(query, list(params.values()))
        return {"count": count}

    def upsert(self, where: Dict, create: Dict, update: Dict) -> Dict:
        existing = self.find_first(where=where)
        if existing:
            return self.update(where=where, data=update) or existing
        return self.create(data=create)

    def aggregate(self, where=None, _count=None, _sum=None, _avg=None, _min=None, _max=None) -> Dict:
        params: Dict = {}
        where_sql = _parse_where(self._model, where, params)
        aggs: List[str] = []
        if _count:
            aggs.append("COUNT(*) AS _count")
        if _sum:
            for f in (_sum if isinstance(_sum, list) else [_sum]):
                aggs.append(f"SUM([{f}]) AS _sum_{f}")
        if _avg:
            for f in (_avg if isinstance(_avg, list) else [_avg]):
                aggs.append(f"AVG([{f}]) AS _avg_{f}")
        if _min:
            for f in (_min if isinstance(_min, list) else [_min]):
                aggs.append(f"MIN([{f}]) AS _min_{f}")
        if _max:
            for f in (_max if isinstance(_max, list) else [_max]):
                aggs.append(f"MAX([{f}]) AS _max_{f}")
        if not aggs:
            aggs = ["COUNT(*) AS _count"]

        query = f"SELECT {', '.join(aggs)} FROM {self._table_sql}"
        if where_sql:
            query += f" WHERE {where_sql}"
        rows = self._adapter.exec(query, list(params.values()))
        return rows[0] if rows else {}

    def vector_search(self, vector: List[float], take: int = 10, where=None, vector_field: str = "embedding", distance_metric: str = "cosine") -> List[Dict]:
        rows = self.find_many(where=where)
        scored = []
        for row in rows:
            raw = row.get(vector_field)
            if raw is None:
                continue
            try:
                vec = json.loads(raw) if isinstance(raw, str) else list(raw)
            except Exception:
                continue
            if not vec or len(vec) != len(vector):
                continue

            dot = sum(a * b for a, b in zip(vector, vec))
            m1 = sum(a ** 2 for a in vector) ** 0.5
            m2 = sum(b ** 2 for b in vec) ** 0.5
            cosine = dot / (m1 * m2) if m1 and m2 else 0.0

            if distance_metric == "cosine":
                dist = 1.0 - cosine
            elif distance_metric == "dot":
                dist = -dot
            else:
                dist = sum((a - b) ** 2 for a, b in zip(vector, vec)) ** 0.5

            scored.append((row, dist))

        scored.sort(key=lambda x: x[1])
        return [{**row, "distance": dist} for row, dist in scored[:take]]


# ─── Factory ─────────────────────────────────────────────────────────────────

def create_an5_adapter(connection_string: str) -> An5Adapter:
    """Create a standalone An5Adapter instance from a connection string."""
    return An5Adapter(connection_string)
