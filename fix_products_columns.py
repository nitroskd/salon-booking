# fix_products_columns.py
import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def fix_products_table():
    """productsテーブルのカラムを確認・修正"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        print("=== productsテーブルの修正を開始 ===\n")
        
        # 既存のカラムを確認
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products'
            ORDER BY ordinal_position
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"既存のカラム: {existing_columns}\n")
        
        # product_name カラムが存在しない場合は name から変更
        if 'product_name' not in existing_columns and 'name' in existing_columns:
            cursor.execute("ALTER TABLE products RENAME COLUMN name TO product_name")
            print("✅ name → product_name に変更しました")
        
        # 必要なカラムを追加
        columns_to_add = {
            'product_name': 'VARCHAR(200) NOT NULL',
            'description': 'TEXT',
            'price': 'DECIMAL(10, 2) NOT NULL',
            'category': 'VARCHAR(50)',
            'stock_quantity': 'INTEGER DEFAULT 0',
            'image_data': 'TEXT',
            'is_active': 'BOOLEAN DEFAULT TRUE',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        print("\n不足しているカラムを追加中...")
        for col_name, col_def in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
                    print(f"  ✅ {col_name} を追加")
                except Exception as e:
                    print(f"  ⚠️  {col_name} スキップ: {e}")
        
        conn.commit()
        print("\n✅ テーブル修正が完了しました！")
        
        # 修正後のカラム一覧を表示
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'products'
            ORDER BY ordinal_position
        """)
        print("\n=== 修正後のカラム一覧 ===")
        for row in cursor.fetchall():
            print(f"  {row[0]:<20} ({row[1]})")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    fix_products_table()