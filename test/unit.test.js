/**
 * mssqlAdapters Unit Tests
 * Tests for TypeScript adapter structure and API.
 * Run: node test/unit.test.js
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    console.log(`  ✗ ${name}`);
    console.log(`    ${err.message}`);
  }
}

function assertIncludes(str, substr, msg) {
  if (!str || !str.includes(substr)) {
    throw new Error(`${msg || 'Assert'}: "${str?.substring(0, 100)}" does not contain "${substr}"`);
  }
}

function assertExists(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
}

console.log('\n=== mssqlAdapters Unit Tests ===\n');

// ─── TypeScript Adapter ──────────────────────────────────────────────────────

console.log('TypeScript Adapter:');

test('mssqlAdapter.ts exists', () => {
  assertExists(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'));
});

test('exports MssqlAdapter class', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'export class MssqlAdapter');
  assertIncludes(content, 'export interface MssqlAdapterConfig');
  assertIncludes(content, 'export function createMssqlAdapter');
});

test('MssqlAdapter has exec method', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'async exec<T = any>(query: string');
});

test('MssqlAdapter has table factory method', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'table<T = any>(modelName: string)');
});

test('MssqlAdapter has transaction support', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, '$transaction');
});

test('MssqlAdapter has connect/disconnect', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, '$connect');
  assertIncludes(content, '$disconnect');
});

test('AdapterTableClient has full CRUD', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'async findMany');
  assertIncludes(content, 'async findFirst');
  assertIncludes(content, 'async findUnique');
  assertIncludes(content, 'async create(');
  assertIncludes(content, 'async update(');
  assertIncludes(content, 'async delete(');
  assertIncludes(content, 'async deleteMany');
  assertIncludes(content, 'async upsert');
});

test('AdapterTableClient has aggregate and groupBy', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'async aggregate');
  assertIncludes(content, 'async groupBy');
});

test('AdapterTableClient has vectorSearch', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'async vectorSearch');
});

test('parseWhere handles OR/AND operators', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, "key === 'OR'");
  assertIncludes(content, "key === 'AND'");
});

test('parseWhere handles comparison operators', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'typescript', 'mssqlAdapter.ts'), 'utf8');
  assertIncludes(content, 'contains');
  assertIncludes(content, 'startsWith');
  assertIncludes(content, 'endsWith');
  assertIncludes(content, 'gte');
  assertIncludes(content, 'lte');
  assertIncludes(content, 'not');
});

// ─── Python Adapter ──────────────────────────────────────────────────────────

console.log('\nPython Adapter:');

test('mssql_adapter.py exists', () => {
  assertExists(path.join(__dirname, '..', 'python', 'mssql_adapter.py'));
});

test('exports MssqlAdapter class', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'python', 'mssql_adapter.py'), 'utf8');
  assertIncludes(content, 'class MssqlAdapter');
  assertIncludes(content, 'class AdapterTableClient');
  assertIncludes(content, 'def create_mssql_adapter');
});

test('Python adapter has CRUD methods', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'python', 'mssql_adapter.py'), 'utf8');
  assertIncludes(content, 'def find_many');
  assertIncludes(content, 'def find_first');
  assertIncludes(content, 'def find_unique');
  assertIncludes(content, 'def create(');
  assertIncludes(content, 'def update(');
  assertIncludes(content, 'def delete(');
  assertIncludes(content, 'def delete_many');
  assertIncludes(content, 'def upsert');
});

test('Python adapter has aggregate and vector_search', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'python', 'mssql_adapter.py'), 'utf8');
  assertIncludes(content, 'def aggregate');
  assertIncludes(content, 'def vector_search');
});

test('Python adapter has transaction support', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'python', 'mssql_adapter.py'), 'utf8');
  assertIncludes(content, 'def transaction');
});

test('Python adapter parses connection string', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'python', 'mssql_adapter.py'), 'utf8');
  assertIncludes(content, 'def _parse_connection_string');
});

// ─── .NET Adapter ────────────────────────────────────────────────────────────

console.log('\n.NET Adapter:');

test('MssqlAdapter.cs exists', () => {
  assertExists(path.join(__dirname, '..', 'dotnet', 'MssqlAdapter.cs'));
});

test('.NET adapter has MssqlAdapter class', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'dotnet', 'MssqlAdapter.cs'), 'utf8');
  assertIncludes(content, 'public class MssqlAdapter');
  assertIncludes(content, 'public class AdapterTableClient<T>');
});

test('.NET adapter has CRUD methods', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'dotnet', 'MssqlAdapter.cs'), 'utf8');
  assertIncludes(content, 'FindMany');
  assertIncludes(content, 'FindFirst');
  assertIncludes(content, 'FindUnique');
  assertIncludes(content, 'Create(');
  assertIncludes(content, 'Update(');
  assertIncludes(content, 'Delete(');
  assertIncludes(content, 'DeleteMany');
  assertIncludes(content, 'Upsert');
});

test('.NET adapter has transaction support', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'dotnet', 'MssqlAdapter.cs'), 'utf8');
  assertIncludes(content, 'BeginTransaction');
  assertIncludes(content, 'Transaction<');
});

test('.NET adapter has VectorSearch', () => {
  const content = fs.readFileSync(path.join(__dirname, '..', 'dotnet', 'MssqlAdapter.cs'), 'utf8');
  assertIncludes(content, 'VectorSearch');
});

// ─── Package & Config ────────────────────────────────────────────────────────

console.log('\nPackage & Config:');

test('package.json is valid', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
  assertIncludes(pkg.name, 'mssql-adapters');
  assertIncludes(pkg.description, 'adapters');
});

test('pyproject.toml exists', () => {
  assertExists(path.join(__dirname, '..', 'pyproject.toml'));
});

test('README.md exists', () => {
  assertExists(path.join(__dirname, '..', 'README.md'));
});

// ─── Summary ─────────────────────────────────────────────────────────────────

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);
process.exit(failed > 0 ? 1 : 0);
