# env_validator.py
"""環境変数のバリデーション"""
import os
import sys

REQUIRED_ENV_VARS = {
    "DATABASE_URL": "PostgreSQL接続URL",
    "ADMIN_USERNAME": "管理者ユーザー名",
    "ADMIN_PASSWORD": "管理者パスワード",
}

OPTIONAL_ENV_VARS = {
    "SENDGRID_API_KEY": "SendGrid APIキー（メール通知用）",
    "GMAIL_USER": "Gmail送信元アドレス",
    "LINE_CHANNEL_ACCESS_TOKEN": "LINE通知用トークン",
    "LINE_USER_ID": "LINE通知先ユーザーID",
    "BASE_URL": "アプリケーションのベースURL",
    "REDIS_URL": "Redisの接続URL（セッション管理用）",
}

def validate_env_vars():
    """環境変数をバリデート"""
    missing_vars = []
    
    # 必須変数のチェック
    for var, description in REQUIRED_ENV_VARS.items():
        if not os.getenv(var):
            missing_vars.append(f"  ❌ {var}: {description}")
    
    if missing_vars:
        print("🚨 以下の必須環境変数が設定されていません:")
        print("\n".join(missing_vars))
        sys.exit(1)
    
    # オプション変数の警告
    missing_optional = []
    for var, description in OPTIONAL_ENV_VARS.items():
        if not os.getenv(var):
            missing_optional.append(f"  ⚠️  {var}: {description}")
    
    if missing_optional:
        print("⚠️  以下のオプション環境変数が設定されていません（機能が制限されます）:")
        print("\n".join(missing_optional))
    
    # セキュリティチェック
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if len(admin_password) < 8:
        print("⚠️  ADMIN_PASSWORDは8文字以上を推奨します")
    
    print("✅ 環境変数のバリデーション完了")

if __name__ == "__main__":
    validate_env_vars()
