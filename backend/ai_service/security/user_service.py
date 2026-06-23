import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.ai_service.core.config import (
    DATABASE_URL, DEFAULT_TENANT_ID, DEFAULT_TENANT_NAME,
    INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_NAME, INITIAL_ADMIN_PASSWORD,
    TENANTS_FILE, USERS_FILE,
)
from backend.ai_service.security.models import User
from backend.ai_service.security.password_service import hash_password, verify_password


class UserService:
    def __init__(
        self, database_url: str = DATABASE_URL, users_file: Path = USERS_FILE,
        tenants_file: Path = TENANTS_FILE,
    ) -> None:
        self.database_url = database_url
        self.users_file = users_file
        self.tenants_file = tenants_file
        if database_url:
            self._ensure_postgres_schema()
        else:
            users_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_default_tenant()
        self._migrate_local_records()
        self._ensure_initial_admin()

    def authenticate(self, email: str, password: str) -> User | None:
        record = self._get_record_by_email(email.strip().lower())
        if not record or not record.get("is_active"):
            return None
        if not verify_password(password, record["password_hash"]):
            return None
        self._touch_last_login(record["id"])
        return self._to_user(record)

    def get_by_id(self, user_id: str) -> User | None:
        record = self._get_record_by_id(user_id)
        return self._to_user(record) if record and record.get("is_active") else None

    def create_tenant(self, name: str, slug: str) -> dict:
        tenant = {
            "id": str(uuid.uuid4()), "name": name.strip(), "slug": slug.strip().lower(),
            "is_active": True, "created_at": datetime.now(UTC).isoformat(),
        }
        if not self.database_url:
            tenants = self._load_tenants()
            if any(item["slug"] == tenant["slug"] for item in tenants):
                raise ValueError("tenant slug already exists")
            tenants.append(tenant); self._save_tenants(tenants); return tenant
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("""INSERT INTO tenants(id,name,slug,is_active,created_at)
                    VALUES(%s::uuid,%s,%s,true,%s::timestamptz)""",
                    (tenant["id"],tenant["name"],tenant["slug"],tenant["created_at"]))
                conn.commit()
        except Exception as exc:
            raise ValueError("tenant slug already exists") from exc
        return tenant

    def create_user(
        self, *, email: str, name: str, password: str, role: str, tenant_id: str,
    ) -> User:
        if role not in {"viewer", "maintainer", "admin"}:
            raise ValueError("invalid role")
        if self._get_record_by_email(email.strip().lower()):
            raise ValueError("email already exists")
        tenant_name = self._tenant_name(tenant_id)
        if not tenant_name:
            raise ValueError("tenant not found")
        record = {
            "id": str(uuid.uuid4()), "email": email.strip().lower(), "name": name.strip(),
            "password_hash": hash_password(password), "role": role, "department": "",
            "is_active": True, "tenant_id": tenant_id, "tenant_name": tenant_name,
            "is_platform_admin": False, "created_at": datetime.now(UTC).isoformat(),
            "last_login_at": None,
        }
        self._insert(record)
        return self._to_user(record)

    def _ensure_initial_admin(self) -> None:
        if self._get_record_by_email(INITIAL_ADMIN_EMAIL):
            return
        self._insert({
            "id": str(uuid.uuid4()), "email": INITIAL_ADMIN_EMAIL,
            "name": INITIAL_ADMIN_NAME, "password_hash": hash_password(INITIAL_ADMIN_PASSWORD),
            "role": "admin", "department": "", "is_active": True,
            "tenant_id": DEFAULT_TENANT_ID, "tenant_name": DEFAULT_TENANT_NAME,
            "is_platform_admin": True,
            "created_at": datetime.now(UTC).isoformat(), "last_login_at": None,
        })

    def _to_user(self, record: dict) -> User:
        return User(id=str(record["id"]), email=record["email"], name=record["name"],
                    role=record["role"], tenant_id=str(record["tenant_id"]),
                    tenant_name=record.get("tenant_name", ""),
                    is_platform_admin=bool(record.get("is_platform_admin", False)),
                    is_active=bool(record["is_active"]))

    def _ensure_default_tenant(self) -> None:
        if not self.database_url:
            tenants = self._load_tenants()
            if not any(item["id"] == DEFAULT_TENANT_ID for item in tenants):
                tenants.append({"id": DEFAULT_TENANT_ID, "name": DEFAULT_TENANT_NAME,
                    "slug": "default", "is_active": True,
                    "created_at": datetime.now(UTC).isoformat()})
                self._save_tenants(tenants)
            return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO tenants(id,name,slug,is_active,created_at)
                VALUES(%s::uuid,%s,'default',true,now()) ON CONFLICT(id) DO NOTHING""",
                (DEFAULT_TENANT_ID, DEFAULT_TENANT_NAME))
            conn.commit()

    def _migrate_local_records(self) -> None:
        if self.database_url or not self.users_file.exists():
            return
        records = self._load(); changed = False
        for record in records:
            if not record.get("tenant_id"):
                record["tenant_id"] = DEFAULT_TENANT_ID; changed = True
            if not record.get("tenant_name"):
                record["tenant_name"] = DEFAULT_TENANT_NAME; changed = True
            if "is_platform_admin" not in record:
                record["is_platform_admin"] = record.get("email") == INITIAL_ADMIN_EMAIL; changed = True
        if changed: self._save(records)

    def _load(self) -> list[dict]:
        if not self.users_file.exists():
            return []
        return json.loads(self.users_file.read_text(encoding="utf-8"))

    def _load_tenants(self) -> list[dict]:
        if not self.tenants_file.exists(): return []
        return json.loads(self.tenants_file.read_text(encoding="utf-8"))

    def _save_tenants(self, records: list[dict]) -> None:
        self.tenants_file.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _tenant_name(self, tenant_id: str) -> str | None:
        if not self.database_url:
            item = next((t for t in self._load_tenants() if t["id"] == tenant_id and t.get("is_active")), None)
            return item["name"] if item else None
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM tenants WHERE id=%s::uuid AND is_active=true", (tenant_id,))
            row = cur.fetchone()
        return row[0] if row else None

    def _save(self, records: list[dict]) -> None:
        self.users_file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_record_by_email(self, email: str) -> dict | None:
        if not self.database_url:
            return next((u for u in self._load() if u["email"] == email), None)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT u.id::text,u.email,u.name,u.password_hash,u.role,u.is_active,
                u.tenant_id::text,t.name,u.is_platform_admin FROM users u JOIN tenants t ON t.id=u.tenant_id
                WHERE u.email=%s""", (email,))
            row = cur.fetchone()
        return self._row(row)

    def _get_record_by_id(self, user_id: str) -> dict | None:
        if not self.database_url:
            return next((u for u in self._load() if u["id"] == user_id), None)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT u.id::text,u.email,u.name,u.password_hash,u.role,u.is_active,
                u.tenant_id::text,t.name,u.is_platform_admin FROM users u JOIN tenants t ON t.id=u.tenant_id
                WHERE u.id=%s::uuid""", (user_id,))
            row = cur.fetchone()
        return self._row(row)

    @staticmethod
    def _row(row) -> dict | None:
        if not row:
            return None
        return dict(zip(("id","email","name","password_hash","role","is_active",
                         "tenant_id","tenant_name","is_platform_admin"), row))

    def _insert(self, record: dict) -> None:
        if not self.database_url:
            records = self._load(); records.append(record); self._save(records); return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO users(id,email,name,password_hash,role,department,is_active,created_at,tenant_id,is_platform_admin)
                VALUES(%s::uuid,%s,%s,%s,%s,%s,%s,%s::timestamptz,%s::uuid,%s)""",
                (record["id"],record["email"],record["name"],record["password_hash"],record["role"],record["department"],record["is_active"],record["created_at"],record["tenant_id"],record["is_platform_admin"]))
            conn.commit()

    def _touch_last_login(self, user_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        if not self.database_url:
            records = self._load()
            for record in records:
                if record["id"] == user_id: record["last_login_at"] = now
            self._save(records); return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET last_login_at=now() WHERE id=%s::uuid", (user_id,)); conn.commit()

    def _ensure_postgres_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS tenants(
                id uuid PRIMARY KEY,name text NOT NULL,slug text UNIQUE NOT NULL,is_active boolean NOT NULL DEFAULT true,
                created_at timestamptz NOT NULL)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS users(
                id uuid PRIMARY KEY,email text UNIQUE NOT NULL,name text NOT NULL,password_hash text NOT NULL,
                role text NOT NULL CHECK(role IN ('viewer','maintainer','admin')),department text NOT NULL DEFAULT '',
                is_active boolean NOT NULL DEFAULT true,created_at timestamptz NOT NULL,last_login_at timestamptz)""")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id uuid")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_platform_admin boolean NOT NULL DEFAULT false")
            cur.execute("UPDATE users SET tenant_id=%s::uuid WHERE tenant_id IS NULL", (DEFAULT_TENANT_ID,))
            cur.execute("ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id)")
            conn.commit()

    def _connect(self):
        import psycopg
        return psycopg.connect(self.database_url)
