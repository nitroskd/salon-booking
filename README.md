# 🌿 Salon Coeur - 予約・商品管理システム

サロン向けの予約管理と商品販売を統合したWebアプリケーション

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.114.0-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)

---

## 📋 目次

- [機能概要](#機能概要)
- [技術スタック](#技術スタック)
- [環境変数](#環境変数)
- [セットアップ](#セットアップ)
- [デプロイ](#デプロイ)
- [使用方法](#使用方法)
- [セキュリティ](#セキュリティ)
- [トラブルシューティング](#トラブルシューティング)

---

## 🎯 機能概要

### ユーザー向け機能
- ✅ オンライン予約フォーム（カレンダー連携）
- ✅ 商品一覧の閲覧（カテゴリー・ブランド別フィルター）
- ✅ 予約完了時のカレンダー登録（Google Calendar / iCal）
- ✅ サロンへのアクセス情報表示

### 管理者向け機能
- ✅ 予約管理（追加・編集・削除）
- ✅ 商品管理（登録・編集・削除）
- ✅ カテゴリー・ブランド管理
- ✅ 営業日・予約時間枠の設定
- ✅ アクセス統計の表示
- ✅ メール/LINE通知（SendGrid / LINE Messaging API）

---

## 🛠️ 技術スタック

### バックエンド
- **FastAPI** - Webフレームワーク
- **PostgreSQL** - データベース
- **psycopg2** - PostgreSQLドライバー

### セキュリティ
- **bcrypt** - パスワードハッシュ化
- **slowapi** - レート制限（ブルートフォース攻撃対策）
- セキュアCookie（HttpOnly, Secure, SameSite）

### 通知
- **SendGrid** - メール送信
- **LINE Messaging API** - LINE通知

### フロントエンド
- HTML5 + CSS3 + JavaScript（Vanilla）
- Jinja2テンプレートエンジン
- レスポンシブデザイン（モバイル対応）

---

## 🔐 環境変数

### 必須

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `DATABASE_URL` | PostgreSQL接続URL | `postgresql://user:pass@host/db` |
| `ADMIN_USERNAME` | 管理者ユーザー名 | `admin` |
| `ADMIN_PASSWORD_HASH` | 管理者パスワード（bcryptハッシュ） | `$2b$12$...` |

### オプション

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `ENVIRONMENT` | 動作環境 | `development` |
| `BASE_URL` | アプリケーションのベースURL | - |
| `SENDGRID_API_KEY` | SendGrid APIキー | - |
| `GMAIL_USER` | メール送信元アドレス | - |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE通知用トークン | - |
| `LINE_USER_ID` | LINE通知先ユーザーID | - |

---

## 🚀 セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd salon-booking
```

### 2. 仮想環境の作成

```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

`.env` ファイルを作成：

```bash
# データベース
DATABASE_URL=postgresql://user:password@localhost/salon_booking

# 管理者認証
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$...  # generate_password_hash.py で生成

# 動作環境
ENVIRONMENT=development

# 通知（オプション）
SENDGRID_API_KEY=your_sendgrid_key
GMAIL_USER=your_email@example.com
LINE_CHANNEL_ACCESS_TOKEN=your_line_token
LINE_USER_ID=your_line_user_id
BASE_URL=http://localhost:8000
```

### 5. データベース初期化

アプリケーション起動時に自動で初期化されます：

```bash
uvicorn main:app --reload
```

起動後、以下のテーブルが自動作成されます：
- `bookings` - 予約
- `products` - 商品
- `categories` - カテゴリー
- `brands` - ブランド
- `available_slots` - 予約時間枠
- `business_hours` - 営業日
- `slot_availability` - 時間枠の有効/無効
- `reminders` - リマインダー
- `page_views` - ページビュー統計

---

## 🌐 デプロイ（Render.com）

### 1. Render.comでサービス作成

1. [Render.com](https://render.com) にログイン
2. "New +" → "Web Service" を選択
3. GitHubリポジトリを接続

### 2. サービス設定

```yaml
Name: salon-booking
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 3. 環境変数の設定

Render.comのダッシュボードで環境変数を設定：

```
DATABASE_URL=<RenderのPostgreSQLのInternal Database URL>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$...
ENVIRONMENT=production
SENDGRID_API_KEY=...
GMAIL_USER=...
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...
BASE_URL=https://your-app.onrender.com
```

### 4. PostgreSQLの作成

1. Render.comで "New +" → "PostgreSQL" を選択
2. データベースを作成
3. "Internal Database URL" をコピーして `DATABASE_URL` に設定

### 5. デプロイ

GitHubにプッシュすると自動デプロイされます：

```bash
git add .
git commit -m "Deploy to production"
git push origin main
```

---

## 📱 使用方法

### ユーザー

1. **予約**
   - トップページから「ご予約はこちら」をクリック
   - フォームに必要事項を入力
   - 予約日時を選択して送信

2. **商品閲覧**
   - トップページから「商品一覧」をクリック
   - カテゴリーやブランドでフィルター可能

### 管理者

1. **ログイン**
   - `/admin/login` にアクセス
   - ユーザー名とパスワードを入力

2. **予約管理**
   - 予約の追加・編集・削除
   - 予約日時順または登録順でソート
   - 過去・今後の予約でフィルター

3. **商品管理**
   - 商品の登録・編集・削除
   - カテゴリー・ブランドの管理
   - セール価格の設定

4. **カレンダー管理**
   - 営業日の設定
   - 時間枠ごとの予約受付制御
   - 定休日の設定

---

## 🔒 セキュリティ

### 実装済みのセキュリティ機能

1. **パスワード保護**
   - bcrypt（12ラウンド）によるハッシュ化
   - 平文パスワードは保存しない

2. **セッション管理**
   - セキュアCookie（HttpOnly, Secure, SameSite）
   - 24時間でタイムアウト
   - ログアウト時に完全削除

3. **レート制限**
   - ログイン: 5回/分
   - 予約: 10回/分
   - API: エンドポイントごとに制限

4. **HTTPS強制**
   - 本番環境では自動的にHTTPS必須
   - TrustedHostMiddlewareで不正なホストをブロック

5. **SQLインジェクション対策**
   - プレースホルダー（`%s`）を使用
   - ユーザー入力を直接SQL文に埋め込まない

### 管理者パスワードの変更

1. ローカルで `generate_password_hash.py` を実行（必要に応じて再作成）

```python
# generate_password_hash.py
import bcrypt
import getpass

password = getpass.getpass("新しいパスワード: ")
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
print(f"ADMIN_PASSWORD_HASH={hashed.decode('utf-8')}")
```

2. Render.comの環境変数 `ADMIN_PASSWORD_HASH` を更新

3. サービスを再起動

---

## 🐛 トラブルシューティング

### ログインできない

**症状:** パスワードが正しいのにログインできない

**原因と対処法:**
1. `ADMIN_PASSWORD_HASH` が正しく設定されているか確認
2. bcryptハッシュが正しいか再生成して確認
3. ログを確認: `⚠️ 平文パスワード比較を使用中` と表示されていないか

### 予約が作成できない

**症状:** 予約フォーム送信後にエラー

**原因と対処法:**
1. `DATABASE_URL` が正しく設定されているか確認
2. データベース接続を確認
3. ログで具体的なエラーを確認

### メール/LINE通知が届かない

**症状:** 予約完了してもメールやLINEが届かない

**原因と対処法:**
1. 環境変数を確認:
   - `SENDGRID_API_KEY`
   - `GMAIL_USER`
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_USER_ID`
2. SendGrid/LINEのAPIキーが有効か確認
3. ログで通知エラーを確認

### レート制限エラー

**症状:** `429 Too Many Requests` エラー

**原因と対処法:**
- 正常な動作です（ブルートフォース攻撃対策）
- 1分待ってから再試行
- 頻繁に発生する場合は `main.py` のレート制限値を調整

### セッションが切れる

**症状:** 管理画面を開いたままにするとログアウトされる

**原因と対処法:**
- 24時間でセッションタイムアウトします（正常動作）
- 再度ログインしてください
- サーバー再起動でもセッションが切れます（現在はメモリ管理のため）

---

## 📊 データベーススキーマ

### bookings（予約）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | SERIAL | 主キー |
| customer_name | VARCHAR(100) | 顧客名 |
| phone_number | VARCHAR(20) | 電話番号 |
| service_name | VARCHAR(100) | サービス名 |
| booking_date | DATE | 予約日 |
| booking_time | TIME | 予約時間 |
| notes | TEXT | 備考 |
| created_at | TIMESTAMP | 作成日時 |

### products（商品）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | SERIAL | 主キー |
| product_name | VARCHAR(200) | 商品名 |
| description | TEXT | 説明 |
| price | DECIMAL(10,2) | 販売価格 |
| original_price | DECIMAL(10,2) | 元値 |
| brand | VARCHAR(100) | ブランド |
| category | VARCHAR(50) | カテゴリー |
| stock_quantity | INTEGER | 在庫数 |
| image_data | TEXT | 画像（Base64） |
| is_active | BOOLEAN | 有効/無効 |
| created_at | TIMESTAMP | 作成日時 |
| updated_at | TIMESTAMP | 更新日時 |

---

## 🔄 アップデート手順

```bash
# 1. 最新コードを取得
git pull origin main

# 2. 依存パッケージを更新
pip install -r requirements.txt

# 3. ローカルで動作確認
uvicorn main:app --reload

# 4. 問題なければデプロイ
git push origin main
```

---

## 📝 ライセンス

このプロジェクトは Salon Coeur 専用です。

---

## 👤 開発者

Salon Coeur 管理チーム

---

## 📞 サポート

問題が発生した場合は、GitHubのIssuesで報告してください。