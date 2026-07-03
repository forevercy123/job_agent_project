"""
用户认证模块：注册、登录、密码加密存储、使用配额管理、管理员审批
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

# 每日使用配额（每项每天上限）
DAILY_QUOTA = {
    "search": 10,  # 岗位检索
    "resume": 5,  # 简历优化
    "interview": 3,  # 面试模拟
}

# 超级管理员用户名（可以改成你想要的，如 "admin"）
ADMIN_USERNAME = "admin"


def _get_conn():
    """获取数据库连接（内部工具函数）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _today_str() -> str:
    """返回今天日期字符串 YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def init_db():
    """
    初始化数据库：创建用户表、使用记录表
    首次运行时自动创建超级管理员账号（需要手动在页面设置密码）
    """
    conn = _get_conn()
    try:
        # ---- 1. 用户表（扩展字段） ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                -- status: pending(待审批) / active(已激活) / blocked(已禁用)
                is_admin INTEGER NOT NULL DEFAULT 0
                -- 1 = 管理员，0 = 普通用户
            )
            """)

        # ---- 2. 使用记录表 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,   -- search / resume / interview
                date TEXT NOT NULL,      -- YYYY-MM-DD
                count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, feature, date)
            )
            """)

        # ---- 3. 操作日志表（简单记录） ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                time TEXT NOT NULL
            )
            """)

        conn.commit()

        # ---- 4. 首次启动自动创建 admin 账号（待设置密码） ----
        existing_admin = conn.execute(
            "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()
        if not existing_admin:
            # 先插入一个"占位"admin 账号，密码后面在页面手动设置
            # 用一个随机复杂密码作为占位，避免被破解
            import secrets

            placeholder_pw = secrets.token_urlsafe(32)
            placeholder_hash = bcrypt.hashpw(
                placeholder_pw.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """INSERT INTO users
                   (username, email, password_hash, created_at, status, is_admin)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (ADMIN_USERNAME, "admin@local", placeholder_hash, now, "active"),
            )
            conn.commit()
            print(f"[Auth] 已创建管理员账号: {ADMIN_USERNAME}（请在页面设置密码）")

        return True
    except Exception as e:
        print(f"[Auth] 数据库初始化失败: {e}")
        return False
    finally:
        conn.close()


# ============================================================
# 密码相关
# ============================================================
def _hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ============================================================
# 注册 / 登录
# ============================================================
def register_user(username: str, password: str, email: str = ""):
    """
    注册新用户 → 新用户默认是「待审批(pending)」状态
    返回: (成功与否, 提示信息)
    """
    username = username.strip()
    password = password.strip()
    email = email.strip()

    if len(username) < 2:
        return False, "用户名至少 2 个字符"
    if len(password) < 6:
        return False, "密码至少 6 个字符"

    if username.lower() == ADMIN_USERNAME.lower():
        return False, "该用户名已被保留，请换一个"

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
            """INSERT INTO users
               (username, email, password_hash, created_at, status, is_admin)
               VALUES (?, ?, ?, ?, 'pending', 0)""",
            (username, email, password_hash, now),
        )
        conn.commit()

        # 记录注册动作
        _log_action(None, "register", f"新用户注册: {username}")

        return (
            True,
            f"✅ 注册成功！账号正在等待管理员审批，" f"审批通过后即可使用全部功能。",
        )
    except Exception as e:
        return False, f"注册失败: {str(e)}"
    finally:
        conn.close()


def login_user(username: str, password: str):
    """
    登录验证：检查密码 + 检查账号状态
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

        # 检查账号状态
        status = user["status"]
        if status == "pending":
            return False, "⏳ 账号正在等待管理员审批，请耐心等待或联系管理员", None
        if status == "blocked":
            return False, "🚫 该账号已被禁用，请联系管理员", None

        # 更新最后登录时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user["id"]))
        conn.commit()

        user_data = {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"] or "",
            "created_at": user["created_at"],
            "last_login": now,
            "status": user["status"],
            "is_admin": bool(user["is_admin"]),
        }
        return True, f"✅ 登录成功！欢迎回来，{username}", user_data
    except Exception as e:
        return False, f"登录失败: {str(e)}", None
    finally:
        conn.close()


# ============================================================
# 管理员重置密码（admin 账号首次使用时设置密码）
# ============================================================
def admin_set_password(new_password: str) -> (bool, str):
    """
    管理员在页面设置自己的密码（首次部署时使用）
    注意：这个函数只能设置 ADMIN_USERNAME 对应的密码
    """
    if len(new_password) < 8:
        return False, "管理员密码至少 8 个字符"

    conn = _get_conn()
    try:
        password_hash = _hash_password(new_password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, ADMIN_USERNAME),
        )
        conn.commit()
        _log_action(None, "admin_password", f"管理员密码已重置")
        return True, "✅ 管理员密码设置成功"
    except Exception as e:
        return False, f"设置失败: {str(e)}"
    finally:
        conn.close()


def admin_needs_password() -> bool:
    """检查 admin 账号是否还在用占位密码（需要设置新密码）"""
    # 简单方式：检查 admin 账号最近是否登录过（last_login 为空 = 从未登录）
    conn = _get_conn()
    try:
        user = conn.execute(
            "SELECT last_login FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()
        return user is not None and not user["last_login"]
    except Exception:
        return True
    finally:
        conn.close()


# ============================================================
# 使用配额管理
# ============================================================
def check_and_increment_quota(user_id: int, feature: str) -> (bool, str):
    """
    检查并更新使用配额（每次调用功能前调用）
    feature: "search" | "resume" | "interview"
    返回: (是否允许, 提示信息)
    """
    if feature not in DAILY_QUOTA:
        return False, "未知功能类型"

    today = _today_str()
    conn = _get_conn()
    try:
        # 查今天该用户对该功能的使用次数
        row = conn.execute(
            """SELECT count FROM usage_log
               WHERE user_id = ? AND feature = ? AND date = ?""",
            (user_id, feature, today),
        ).fetchone()

        current_count = row["count"] if row else 0
        max_count = DAILY_QUOTA[feature]

        if current_count >= max_count:
            feature_name = {
                "search": "岗位检索",
                "resume": "简历优化",
                "interview": "面试模拟",
            }[feature]
            return (
                False,
                f"📊 今日{feature_name}已达上限（{max_count}次/天），请明天再来",
            )

        # 更新或插入记录
        if row:
            conn.execute(
                """UPDATE usage_log SET count = count + 1
                   WHERE user_id = ? AND feature = ? AND date = ?""",
                (user_id, feature, today),
            )
        else:
            conn.execute(
                """INSERT INTO usage_log (user_id, feature, date, count)
                   VALUES (?, ?, ?, 1)""",
                (user_id, feature, today),
            )
        conn.commit()

        # 记录到操作日志
        _log_action(user_id, feature, f"功能调用: {feature}（第{current_count + 1}次）")

        remaining = max_count - current_count - 1
        return True, f"✅ 可用次数剩余: {remaining}/{max_count}"
    except Exception as e:
        return False, f"配额检查失败: {str(e)}"
    finally:
        conn.close()


def get_user_usage(user_id: int) -> dict:
    """获取当前用户今日各项使用情况（在侧边栏展示）"""
    today = _today_str()
    conn = _get_conn()
    usage = {}
    try:
        for feature in DAILY_QUOTA.keys():
            row = conn.execute(
                """SELECT count FROM usage_log
                   WHERE user_id = ? AND feature = ? AND date = ?""",
                (user_id, feature, today),
            ).fetchone()
            used = row["count"] if row else 0
            usage[feature] = {
                "used": used,
                "max": DAILY_QUOTA[feature],
                "remaining": max(0, DAILY_QUOTA[feature] - used),
            }
        return usage
    except Exception:
        return {}
    finally:
        conn.close()


# ============================================================
# 管理员后台功能
# ============================================================
def get_all_users() -> list:
    """获取所有用户列表（管理员用）"""
    conn = _get_conn()
    try:
        rows = conn.execute("""SELECT id, username, email, status, is_admin,
                      created_at, last_login
               FROM users ORDER BY id DESC""").fetchall()
        users = []
        for r in rows:
            # 查总使用次数
            total_usage = conn.execute(
                "SELECT IFNULL(SUM(count), 0) AS s FROM usage_log WHERE user_id = ?",
                (r["id"],),
            ).fetchone()
            users.append(
                {
                    "id": r["id"],
                    "username": r["username"],
                    "email": r["email"] or "-",
                    "status": r["status"],
                    "is_admin": bool(r["is_admin"]),
                    "created_at": r["created_at"],
                    "last_login": r["last_login"] or "-",
                    "total_usage": total_usage["s"] if total_usage else 0,
                }
            )
        return users
    except Exception as e:
        print(f"[Auth] 获取用户列表失败: {e}")
        return []
    finally:
        conn.close()


def admin_update_user_status(user_id: int, new_status: str) -> (bool, str):
    """管理员修改用户状态: pending / active / blocked"""
    if new_status not in ("pending", "active", "blocked"):
        return False, "无效的状态值"

    # 不允许修改自己
    conn = _get_conn()
    try:
        user = conn.execute(
            "SELECT username, is_admin FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return False, "用户不存在"
        if user["is_admin"]:
            return False, "不允许修改管理员账号状态"

        conn.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        _log_action(None, "admin", f"修改用户{user['username']}状态为 {new_status}")

        status_text = {"pending": "待审批", "active": "已激活", "blocked": "已禁用"}
        return (
            True,
            f"✅ 已将用户 {user['username']} 状态更新为: {status_text[new_status]}",
        )
    except Exception as e:
        return False, f"操作失败: {str(e)}"
    finally:
        conn.close()


def admin_delete_user(user_id: int) -> (bool, str):
    """管理员删除用户（连同使用记录）"""
    conn = _get_conn()
    try:
        user = conn.execute(
            "SELECT username, is_admin FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return False, "用户不存在"
        if user["is_admin"]:
            return False, "不允许删除管理员账号"

        conn.execute("DELETE FROM usage_log WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM action_log WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        _log_action(None, "admin", f"删除用户: {user['username']}")
        return True, f"✅ 已删除用户 {user['username']}"
    except Exception as e:
        return False, f"删除失败: {str(e)}"
    finally:
        conn.close()


# ============================================================
# 工具函数
# ============================================================
def _log_action(user_id, action, detail):
    """记录一条操作日志（内部工具函数）"""
    conn = _get_conn()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO action_log (user_id, action, detail, time) VALUES (?, ?, ?, ?)",
            (user_id, action, detail, now),
        )
        conn.commit()
    except Exception:
        pass
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


def get_pending_user_count() -> int:
    """获取待审批用户数量（在侧边栏提示管理员）"""
    conn = _get_conn()
    try:
        result = conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE status = 'pending'"
        ).fetchone()
        return result["cnt"] if result else 0
    except Exception:
        return 0
    finally:
        conn.close()
