-- Run this in Supabase SQL Editor after creating the schema.
-- Replace password_hash values with hashes generated locally:
--   .\.venv\Scripts\python.exe -c "import bcrypt; print(bcrypt.hashpw(b'Officer@123', bcrypt.gensalt()).decode())"
--   .\.venv\Scripts\python.exe -c "import bcrypt; print(bcrypt.hashpw(b'Admin@123', bcrypt.gensalt()).decode())"

INSERT INTO staff (name, email, password_hash, role, commune)
VALUES
  ('Nodal Officer', 'officer@puducherry.gov.in', 'Officer@123', 'nodal_officer', 'Puducherry'),
  ('Admin', 'admin@pondysevai.in', 'Admin@123', 'admin', 'Puducherry')
ON CONFLICT (email) DO UPDATE SET
  name = EXCLUDED.name,
  password_hash = EXCLUDED.password_hash,
  role = EXCLUDED.role,
  commune = EXCLUDED.commune;
