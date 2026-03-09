# PostgreSQL setup for Vocence

## 1. Install PostgreSQL (if not already installed)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
```

**Fedora/RHEL:**
```bash
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
```

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

## 2. Create user and database

Switch to the `postgres` system user and run `psql`, then run:

```sql
-- Create user with password
CREATE USER vocence WITH PASSWORD 'vocence';

-- Create database owned by vocence
CREATE DATABASE vocence OWNER vocence;

-- Optional: grant all privileges (usually OWNER is enough)
GRANT ALL PRIVILEGES ON DATABASE vocence TO vocence;

-- Allow vocence to create objects in public schema (PostgreSQL 15+)
\c vocence
GRANT ALL ON SCHEMA public TO vocence;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vocence;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vocence;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vocence;
```

## 3. One-liner from your shell (no interactive psql)

Run this as a user that can run `psql` as `postgres` (often need `sudo -u postgres`):

```bash
sudo -u postgres psql -c "CREATE USER vocence WITH PASSWORD 'vocence';" -c "CREATE DATABASE vocence OWNER vocence;" -c "\c vocence" -c "GRANT ALL ON SCHEMA public TO vocence;"
```

## 4. Test the connection

```bash
psql -h localhost -U vocence -d vocence -W
# Enter password: vocence
```

Or with connection string:
```
postgresql://vocence:vocence@localhost:5432/vocence
```

## 5. If PostgreSQL uses peer auth (Linux default)

By default, Linux often allows only the `postgres` system user to connect. To allow password login for `vocence` from localhost, edit `pg_hba.conf`:

1. Find config (often `/etc/postgresql/16/main/pg_hba.conf` or `/var/lib/pgsql/data/pg_hba.conf`).
2. Add or change a line for local connections:
   ```
   # TYPE  DATABASE  USER    ADDRESS      METHOD
   host    vocence   vocence 127.0.0.1/32 scram-sha-256
   ```
3. Restart PostgreSQL:
   ```bash
   sudo systemctl restart postgresql
   ```

Then the connection string `postgresql://vocence:vocence@localhost:5432/vocence` will work.
