# generate_password_hash.py
"""
パスワードをbcryptでハッシュ化するスクリプト
使い方: python generate_password_hash.py
"""
import bcrypt
import getpass

def generate_hash():
    print("=" * 50)
    print("パスワードハッシュ生成ツール")
    print("=" * 50)
    
    password = getpass.getpass("ハッシュ化するパスワードを入力: ")
    
    if len(password) < 8:
        print("⚠️  警告: パスワードは8文字以上を推奨します")
        confirm = input("続行しますか？ (y/n): ")
        if confirm.lower() != 'y':
            print("中止しました")
            return
    
    # bcryptでハッシュ化
    salt = bcrypt.gensalt(rounds=12)  # 12ラウンド（セキュアだが高速）
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    hashed_str = hashed.decode('utf-8')
    
    print("\n" + "=" * 50)
    print("✅ ハッシュ化完了")
    print("=" * 50)
    print("\n以下のハッシュを環境変数に設定してください:")
    print(f"\nADMIN_PASSWORD_HASH={hashed_str}")
    print("\n注意:")
    print("- ADMIN_PASSWORDは削除してください")
    print("- ADMIN_PASSWORD_HASHを代わりに使用します")
    print("=" * 50)
    
    # 検証テスト
    print("\n🔍 検証テスト中...")
    if bcrypt.checkpw(password.encode('utf-8'), hashed):
        print("✅ 検証成功: ハッシュは正しく生成されました")
    else:
        print("❌ 検証失敗: 何か問題が発生しました")

if __name__ == "__main__":
    try:
        generate_hash()
    except KeyboardInterrupt:
        print("\n\n中止しました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
