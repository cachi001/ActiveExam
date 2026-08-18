// Seed minimo de 3 usuarios con credencial local (canonico, alineado con el seed
// del backend: ADMIN-001 / EST-001 / PROC-001).
//
// Uso (desde la raiz del repo):
//   ALLOW_MUTATION=1 railway run --service Postgres -- node tools/db/seed_users.js
//
// Crea o actualiza el password (idempotente — re-correr es seguro):
//   admin@activeexam.local       rol admin_sistema   password Admin123
//   estudiante@activeexam.local  rol estudiante      password Estudiante123
//   proctor@activeexam.local     rol proctor         password Proctor123
//
// El hash se calcula con bcryptjs a 12 rounds — equivalente al bcrypt 12r de
// passlib que usa el backend en POST /api/v1/users. auth_provider='local'.

import pg from 'pg';
import bcrypt from 'bcryptjs';

const SEEDS = [
  {
    username: 'ADMIN-001',
    email: 'admin@activeexam.local',
    password: 'Admin123',
    roles: ['admin_sistema'],
    nombre: 'Admin',
    apellido: 'Sistema',
  },
  {
    username: 'EST-001',
    email: 'estudiante@activeexam.local',
    password: 'Estudiante123',
    roles: ['estudiante'],
    nombre: 'Estudiante',
    apellido: 'Prueba',
  },
  {
    username: 'PROC-001',
    email: 'proctor@activeexam.local',
    password: 'Proctor123',
    roles: ['proctor'],
    nombre: 'Proctor',
    apellido: 'Prueba',
  },
];

if (process.env.ALLOW_MUTATION !== '1') {
  console.error('[guard] Este script inserta usuarios. Re-ejecutalo con ALLOW_MUTATION=1.');
  process.exit(3);
}

let url = process.env.DATABASE_PUBLIC_URL ?? process.env.DATABASE_URL ?? '';
if (!url) {
  console.error('DATABASE_PUBLIC_URL / DATABASE_URL no estan definidos.');
  process.exit(2);
}
url = url.replace('+asyncpg', '');

const client = new pg.Client({
  connectionString: url,
  ssl: { rejectUnauthorized: false },
});

await client.connect();
try {
  for (const u of SEEDS) {
    const hash = await bcrypt.hash(u.password, 12);
    const res = await client.query(
      `INSERT INTO usuario
         (username, email, roles, password_hash, auth_provider, nombre, apellido, attrs_federados)
       VALUES ($1, $2, $3::jsonb, $4, 'local', $5, $6, '{}'::jsonb)
       ON CONFLICT (username) DO UPDATE SET
         password_hash = EXCLUDED.password_hash,
         roles = EXCLUDED.roles,
         nombre = EXCLUDED.nombre,
         apellido = EXCLUDED.apellido,
         eliminado_en = NULL
       RETURNING (xmax = 0) AS inserted`,
      [
        u.username,
        u.email,
        JSON.stringify(u.roles),
        hash,
        u.nombre,
        u.apellido,
      ],
    );
    const status = res.rows[0]?.inserted ? 'CREATED' : 'UPDATED';
    console.log(`${status}  ${u.email.padEnd(34)} roles=${JSON.stringify(u.roles)}`);
  }
} finally {
  await client.end();
}
