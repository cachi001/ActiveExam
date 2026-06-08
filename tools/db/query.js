// Ejecuta SQL ad-hoc contra la DB de Railway sin exponer el DATABASE_URL.
//
// Uso:
//   railway run --service ActiveExam -- node tools/db/query.js "SELECT 1"
//
// Lee la query de argv[2]. Soporta DSN postgres:// y postgresql://, normaliza
// el driver `+asyncpg` (lo usa el backend Python). Imprime el resultado como
// tabla (psql-like). Falla limpio si la query toca > 1 fila sin LIMIT explícito
// y `--allow-mass=1` no está en el env (capa de seguridad para evitar borrados
// accidentales por mi parte).

import pg from 'pg';

const sql = process.argv[2];
if (!sql) {
  console.error('Usage: node tools/db/query.js "<SQL>"');
  process.exit(2);
}

// Cuando corremos vía `railway run --service ActiveExam`, sólo está expuesto el
// hostname INTERNO (postgres.railway.internal) que no resuelve desde fuera de
// la VPC de Railway. Para conectar desde mi máquina necesito DATABASE_PUBLIC_URL
// (alias del proxy TCP que Railway expone). Si está, gana; si no, caemos a la
// URL normal y avisamos por stderr.
let url =
  process.env.DATABASE_PUBLIC_URL ??
  process.env.DATABASE_URL ??
  '';
if (!url) {
  console.error(
    'DATABASE_PUBLIC_URL / DATABASE_URL no están definidos en el entorno.\n' +
      'Probá: railway run --service Postgres -- node tools/db/query.js "..."',
  );
  process.exit(2);
}
// El backend usa postgresql+asyncpg://...; node-pg no entiende el sufijo.
url = url.replace('+asyncpg', '');

const client = new pg.Client({
  connectionString: url,
  ssl: { rejectUnauthorized: false },
});

const isMutating = /^\s*(update|delete|insert|drop|truncate|alter)\b/i.test(sql);
if (isMutating && process.env.ALLOW_MUTATION !== '1') {
  console.error(
    '[guard] Esta query parece mutar datos. Re-ejecutá con ALLOW_MUTATION=1 si es intencional:',
  );
  console.error('        ALLOW_MUTATION=1 railway run --service ActiveExam -- node tools/db/query.js "..."');
  process.exit(3);
}

await client.connect();
try {
  const res = await client.query(sql);
  if (Array.isArray(res)) {
    res.forEach((r, i) => imprimir(r, `Statement ${i + 1}`));
  } else {
    imprimir(res, 'Statement');
  }
} finally {
  await client.end();
}

function imprimir(res, etiqueta) {
  console.log(`\n=== ${etiqueta} (${res.command ?? '?'}) — ${res.rowCount ?? 0} filas ===`);
  if (res.rows && res.rows.length > 0) {
    console.table(res.rows);
  } else if (res.command && !/SELECT/i.test(res.command)) {
    console.log('(sin output de filas)');
  }
}
