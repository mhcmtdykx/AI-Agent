"""
用户认证模块 - JWT Token 认证 + 用户数据隔离
"""
import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from functools import wraps

# JWT 简单实现（不依赖 PyJWT）
import base64
import hmac


class UserManager:
    """用户管理器"""

    def __init__(self, storage_path: str = "user_storage"):
        self.storage_path = storage_path
        self.users_file = os.path.join(storage_path, "users.json")
        self.secret_key = self._load_or_create_secret()
        self.users: Dict[str, dict] = {}
        os.makedirs(storage_path, exist_ok=True)
        self._load_users()

    def _load_or_create_secret(self) -> str:
        """加载或创建 JWT 密钥"""
        secret_file = os.path.join(self.storage_path, ".secret_key")
        os.makedirs(self.storage_path, exist_ok=True)
        if os.path.exists(secret_file):
            with open(secret_file, 'r') as f:
                return f.read().strip()
        secret = secrets.token_hex(32)
        with open(secret_file, 'w') as f:
            f.write(secret)
        return secret

    def _load_users(self):
        """加载用户数据"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            except Exception:
                self.users = {}

    def _save_users(self):
        """保存用户数据"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    def _hash_password(self, password: str, salt: str = None) -> tuple:
        """哈希密码"""
        if salt is None:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hashed.hex(), salt

    def register(self, username: str, password: str, email: str = None) -> Dict:
        """注册用户"""
        if not username or len(username) < 2:
            return {"success": False, "error": "用户名至少2个字符"}
        if not password or len(password) < 6:
            return {"success": False, "error": "密码至少6个字符"}
        if username in self.users:
            return {"success": False, "error": "用户名已存在"}

        hashed_password, salt = self._hash_password(password)
        user_id = secrets.token_hex(8)
        self.users[username] = {
            "user_id": user_id,
            "username": username,
            "password_hash": hashed_password,
            "salt": salt,
            "email": email,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        self._save_users()

        # 创建用户数据目录
        user_data_dir = os.path.join(self.storage_path, "data", user_id)
        os.makedirs(user_data_dir, exist_ok=True)

        return {"success": True, "user_id": user_id, "username": username}

    def login(self, username: str, password: str) -> Dict:
        """用户登录"""
        if username not in self.users:
            return {"success": False, "error": "用户名或密码错误"}

        user = self.users[username]
        hashed_password, _ = self._hash_password(password, user["salt"])

        if hashed_password != user["password_hash"]:
            return {"success": False, "error": "用户名或密码错误"}

        # 更新最后登录时间
        user["last_login"] = datetime.now().isoformat()
        self._save_users()

        # 生成 JWT token
        token = self._generate_token(username, user["user_id"])

        return {
            "success": True,
            "token": token,
            "user_id": user["user_id"],
            "username": username
        }

    def _generate_token(self, username: str, user_id: str) -> str:
        """生成 JWT Token"""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user_id,
            "username": username,
            "iat": datetime.utcnow().isoformat(),
            "exp": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')

        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
        signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip('=')

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def verify_token(self, token: str) -> Optional[Dict]:
        """验证 JWT Token"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None

            header_b64, payload_b64, signature_b64 = parts

            # 验证签名
            message = f"{header_b64}.{payload_b64}"
            expected_sig = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
            expected_sig_b64 = base64.urlsafe_b64encode(expected_sig.encode()).decode().rstrip('=')

            if signature_b64 != expected_sig_b64:
                return None

            # 解析 payload
            # 补充 base64 padding
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            # 检查过期时间
            exp = datetime.fromisoformat(payload["exp"])
            if datetime.utcnow() > exp:
                return None

            return payload
        except Exception:
            return None

    def get_user_data_dir(self, user_id: str) -> str:
        """获取用户数据目录"""
        user_dir = os.path.join(self.storage_path, "data", user_id)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_user_id_by_username(self, username: str) -> Optional[str]:
        """根据用户名获取用户ID"""
        if username in self.users:
            return self.users[username]["user_id"]
        return None


# 全局用户管理器实例
user_manager = UserManager()


def get_user_manager() -> UserManager:
    """获取用户管理器"""
    return user_manager
