// MssqlAdapter.cs
// Standalone .NET runtime adapter for MSSQL ORM.
// Provides connection, query execution, and typed TableClient<T>.
// Works independently - no EF Core dependency.
//
// Usage:
//   var db = new MssqlAdapter(connectionString);
//   var users = db.Table<User>("dbo.users").FindMany("IsActive = @p", new { p = true });

using System;
using System.Collections.Generic;
using System.Data;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Microsoft.Data.SqlClient;

namespace MssqlOrm
{
    // ─── Config ────────────────────────────────────────────────────────────────

    public class MssqlAdapterOptions
    {
        public string ConnectionString { get; set; }
        public int CommandTimeout { get; set; } = 60;
        public int ConnectRetryCount { get; set; } = 3;
    }

    // ─── Adapter ────────────────────────────────────────────────────────────────

    public class MssqlAdapter : IDisposable
    {
        public string ConnectionString { get; }
        private readonly int _commandTimeout;

        [ThreadStatic]
        private static SqlConnection _txConn;
        [ThreadStatic]
        private static SqlTransaction _tx;

        public MssqlAdapter(string connectionString, int commandTimeout = 60)
        {
            ConnectionString = connectionString ?? throw new ArgumentNullException(nameof(connectionString));
            _commandTimeout = commandTimeout;
        }

        public MssqlAdapter(MssqlAdapterOptions options) : this(options.ConnectionString, options.CommandTimeout) { }

        // ── Connection management ──────────────────────────────────────────────

        private SqlConnection OpenConnection(out bool isInTransaction)
        {
            if (_txConn != null) { isInTransaction = true; return _txConn; }
            isInTransaction = false;
            var conn = new SqlConnection(ConnectionString);
            conn.Open();
            return conn;
        }

        private static SqlTransaction ActiveTransaction => _tx;

        private SqlCommand BuildCommand(SqlConnection conn, string sql, Dictionary<string, object> parameters = null)
        {
            var cmd = new SqlCommand(sql, conn) { CommandTimeout = _commandTimeout };
            if (ActiveTransaction != null) cmd.Transaction = ActiveTransaction;
            if (parameters != null)
            {
                foreach (var kv in parameters)
                {
                    var paramName = kv.Key.StartsWith("@") ? kv.Key : "@" + kv.Key;
                    cmd.Parameters.AddWithValue(paramName, kv.Value ?? DBNull.Value);
                }
            }
            return cmd;
        }

        // ── Raw query execution ────────────────────────────────────────────────

        public List<Dictionary<string, object>> QueryRaw(string sql, Dictionary<string, object> parameters = null)
        {
            var results = new List<Dictionary<string, object>>();
            var conn = OpenConnection(out bool isTx);
            try
            {
                using var cmd = BuildCommand(conn, sql, parameters);
                using var reader = cmd.ExecuteReader();
                while (reader.Read())
                {
                    var row = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
                    for (int i = 0; i < reader.FieldCount; i++)
                    {
                        row[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
                    }
                    results.Add(row);
                }
            }
            finally { if (!isTx) conn.Dispose(); }
            return results;
        }

        public List<T> QueryRaw<T>(string sql, Dictionary<string, object> parameters = null) where T : new()
        {
            var results = new List<T>();
            var conn = OpenConnection(out bool isTx);
            try
            {
                using var cmd = BuildCommand(conn, sql, parameters);
                using var reader = cmd.ExecuteReader();
                var props = typeof(T).GetProperties(BindingFlags.Public | BindingFlags.Instance);
                while (reader.Read())
                {
                    var item = new T();
                    foreach (var prop in props)
                    {
                        if (!HasColumn(reader, prop.Name)) continue;
                        var val = reader[prop.Name];
                        if (val == DBNull.Value) continue;
                        try { prop.SetValue(item, Convert.ChangeType(val, prop.PropertyType)); } catch { }
                    }
                    results.Add(item);
                }
            }
            finally { if (!isTx) conn.Dispose(); }
            return results;
        }

        public int ExecuteRaw(string sql, Dictionary<string, object> parameters = null)
        {
            var conn = OpenConnection(out bool isTx);
            try
            {
                using var cmd = BuildCommand(conn, sql, parameters);
                return cmd.ExecuteNonQuery();
            }
            finally { if (!isTx) conn.Dispose(); }
        }

        // ── Transaction ────────────────────────────────────────────────────────

        public MssqlTransaction BeginTransaction()
        {
            var conn = new SqlConnection(ConnectionString);
            conn.Open();
            var tx = conn.BeginTransaction();
            _txConn = conn;
            _tx = tx;
            return new MssqlTransaction(conn, tx, () => { _txConn = null; _tx = null; });
        }

        public TResult Transaction<TResult>(Func<MssqlAdapter, TResult> fn)
        {
            using var txScope = BeginTransaction();
            try
            {
                var result = fn(this);
                txScope.Commit();
                return result;
            }
            catch
            {
                txScope.Rollback();
                throw;
            }
        }

        // ── Table client factory ───────────────────────────────────────────────

        public AdapterTableClient<T> Table<T>(string tableName) where T : new()
            => new AdapterTableClient<T>(this, tableName);

        // ── Utilities ──────────────────────────────────────────────────────────

        private static bool HasColumn(SqlDataReader reader, string name)
        {
            for (int i = 0; i < reader.FieldCount; i++)
                if (reader.GetName(i).Equals(name, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public void Dispose() { }
    }

    // ─── Typed Table Client ────────────────────────────────────────────────────

    public class AdapterTableClient<T> where T : new()
    {
        private readonly MssqlAdapter _adapter;
        private readonly string _tableName;

        public AdapterTableClient(MssqlAdapter adapter, string tableName)
        {
            _adapter = adapter;
            _tableName = tableName;
        }

        public List<T> FindMany(string whereClause = null, Dictionary<string, object> parameters = null,
            string orderBy = null, int? skip = null, int? take = null)
        {
            var sb = new StringBuilder($"SELECT * FROM {_tableName} WITH (NOLOCK)");
            if (!string.IsNullOrEmpty(whereClause)) sb.Append($" WHERE {whereClause}");
            if (!string.IsNullOrEmpty(orderBy)) sb.Append($" ORDER BY {orderBy}");
            if (skip.HasValue && take.HasValue)
                sb.Append($" OFFSET {skip.Value} ROWS FETCH NEXT {take.Value} ROWS ONLY");
            else if (take.HasValue)
                sb.Append($" OFFSET 0 ROWS FETCH NEXT {take.Value} ROWS ONLY");

            return _adapter.QueryRaw<T>(sb.ToString(), parameters);
        }

        public T FindFirst(string whereClause = null, Dictionary<string, object> parameters = null, string orderBy = null)
        {
            var rows = FindMany(whereClause, parameters, orderBy, skip: null, take: 1);
            return rows.Count > 0 ? rows[0] : default;
        }

        public T FindUnique(object id, string idColumnName = "Id")
        {
            return FindFirst($"{idColumnName} = @id", new Dictionary<string, object> { { "id", id } });
        }

        public int Count(string whereClause = null, Dictionary<string, object> parameters = null)
        {
            var sql = $"SELECT COUNT(*) FROM {_tableName}";
            if (!string.IsNullOrEmpty(whereClause)) sql += $" WHERE {whereClause}";
            var rows = _adapter.QueryRaw(sql, parameters);
            if (rows.Count > 0)
            {
                var val = rows[0].Values.GetEnumerator();
                val.MoveNext();
                return Convert.ToInt32(val.Current);
            }
            return 0;
        }

        public T Create(T entity)
        {
            var props = typeof(T).GetProperties(BindingFlags.Public | BindingFlags.Instance);
            var cols = new List<string>();
            var vals = new List<string>();
            var parameters = new Dictionary<string, object>();

            foreach (var prop in props)
            {
                var val = prop.GetValue(entity);
                if (val == null) continue;
                cols.Add(prop.Name);
                vals.Add("@" + prop.Name);
                parameters["@" + prop.Name] = val;
            }

            var sql = $"INSERT INTO {_tableName} ({string.Join(", ", cols)}) VALUES ({string.Join(", ", vals)})";
            _adapter.ExecuteRaw(sql, parameters);
            return entity;
        }

        public T Update(T entity, string idColumnName = "Id")
        {
            var props = typeof(T).GetProperties(BindingFlags.Public | BindingFlags.Instance);
            var sets = new List<string>();
            var parameters = new Dictionary<string, object>();
            object idVal = null;

            foreach (var prop in props)
            {
                var val = prop.GetValue(entity);
                if (prop.Name.Equals(idColumnName, StringComparison.OrdinalIgnoreCase))
                {
                    idVal = val;
                }
                else if (val != null)
                {
                    sets.Add($"{prop.Name} = @{prop.Name}");
                    parameters["@" + prop.Name] = val;
                }
            }

            if (idVal == null) throw new InvalidOperationException($"Cannot update entity without {idColumnName}");
            parameters["@_id"] = idVal;
            var sql = $"UPDATE {_tableName} SET {string.Join(", ", sets)} WHERE {idColumnName} = @_id";
            _adapter.ExecuteRaw(sql, parameters);
            return entity;
        }

        public bool Delete(object id, string idColumnName = "Id")
        {
            var sql = $"DELETE FROM {_tableName} WHERE {idColumnName} = @id";
            var n = _adapter.ExecuteRaw(sql, new Dictionary<string, object> { { "@id", id } });
            return n > 0;
        }

        public int DeleteMany(string whereClause = null, Dictionary<string, object> parameters = null)
        {
            var sql = $"DELETE FROM {_tableName}";
            if (!string.IsNullOrEmpty(whereClause)) sql += $" WHERE {whereClause}";
            return _adapter.ExecuteRaw(sql, parameters);
        }

        public T Upsert(T entity, string idColumnName = "Id")
        {
            var idProp = typeof(T).GetProperty(idColumnName, BindingFlags.Public | BindingFlags.Instance | BindingFlags.IgnoreCase);
            if (idProp == null) throw new InvalidOperationException($"Property {idColumnName} not found on {typeof(T).Name}");
            var idVal = idProp.GetValue(entity);
            var existing = idVal != null ? FindUnique(idVal, idColumnName) : default;
            if (existing != null) return Update(entity, idColumnName);
            return Create(entity);
        }

        // ── Vector Search ──────────────────────────────────────────────────────

        public List<(T Item, double Distance)> VectorSearch(
            List<double> vector, int take = 10,
            string whereClause = null, Dictionary<string, object> parameters = null,
            string vectorField = "Embedding", string distanceMetric = "cosine")
        {
            var rows = FindMany(whereClause, parameters);
            var results = new List<(T, double)>();
            var vectorProp = typeof(T).GetProperty(vectorField, BindingFlags.Public | BindingFlags.Instance | BindingFlags.IgnoreCase);
            if (vectorProp == null) return results;

            foreach (var row in rows)
            {
                var rawVal = vectorProp.GetValue(row);
                if (rawVal == null) continue;
                List<double> vec = null;
                try
                {
                    if (rawVal is string s) vec = JsonSerializer.Deserialize<List<double>>(s);
                }
                catch { continue; }
                if (vec == null || vec.Count != vector.Count) continue;

                double dot = 0, m1 = 0, m2 = 0;
                for (int i = 0; i < vector.Count; i++)
                {
                    dot += vector[i] * vec[i];
                    m1 += vector[i] * vector[i];
                    m2 += vec[i] * vec[i];
                }
                double cosine = (m1 > 0 && m2 > 0) ? dot / (Math.Sqrt(m1) * Math.Sqrt(m2)) : 0;
                double dist = distanceMetric == "cosine" ? 1.0 - cosine :
                              distanceMetric == "dot" ? -dot : Math.Sqrt(vector.Count);
                results.Add((row, dist));
            }

            results.Sort((a, b) => a.Item2.CompareTo(b.Item2));
            return results.GetRange(0, Math.Min(take, results.Count));
        }
    }
}
