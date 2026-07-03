"""
用户认证模块：注册、登录、密码加密存储
使用 SQLite 数据库存储用户信息，bcrypt 加密密码
"""

import sqlite3
import bcrypt
import os
from datetime import datetime

# 数据库文件路径（放在项目根目录）
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "users.db"
)


def _get_conn():
    """获取数据库连接（内部工具函数）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化用户表（首次运行时调用）"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
            """)
        conn.commit()
        return True
    except Exception as e:
        print(f"[Auth] 数据库初始化失败: {e}")
        return False
    finally:
        conn.close()


def _hash_password(password: str) -> str:
    """将明文密码加密为哈希值"""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def register_user(username: str, password: str, email: str = ""):
    """
    注册新用户
    返回: (成功与否, 提示信息)
    """
    username = username.strip()
    password = password.strip()
    email = email.strip()

    if len(username) < 2:
        return False, "用户名至少 2 个字符"
    if len(password) < 6:
        return False, "密码至少 6 个字符"

    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return False, f"用户名 {username} 已被注册"

        if email:
            existing_email = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing_email:
                return False, "该邮箱已被注册"

        password_hash = _hash_password(password)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, now),
        )
        conn.commit()
        return True, f"✅ 注册成功！欢迎 {username}"
    except Exception as e:
        return False, f"注册失败: {str(e)}"
    finally:
        conn.close()


def login_user(username: str, password: str):
    """
    登录验证
    返回: (成功与否, 提示信息, 用户数据字典)
    """
    username = username.strip()
    password = password.strip()

    if not username or not password:
        return False, "请输入用户名和密码", None

    conn = _get_conn()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if not user:
            return False, "用户名不存在", None

        if not _verify_password(password, user["password_hash"]):
            return False, "密码错误", None

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user["id"]))
        conn.commit()

        user_data = {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"] or "",
            "created_at": user["created_at"],
            "last_login": now,
        }
        return True, f"✅ 登录成功！欢迎回来，{username}", user_data
    except Exception as e:
        return False, f"登录失败: {str(e)}", None
    finally:
        conn.close()


def get_user_count() -> int:
    """获取当前注册用户总数"""
    conn = _get_conn()
    try:
        result = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return result["cnt"] if result else 0
    except Exception:
        return 0
    finally:
        conn.close()
