import psycopg2

DATABASE_URL = "postgresql://salon_user:BEyvekh0RfDA28GMKiSEzog0N7f4vdkP@dpg-d3trfagdl3ps73emkmd0-a/salon_booking_40b0"

def fix_table():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        print("=== テーブル修正を開始 ===\n")
        
        # 既存カラムを確認
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'products'
            ORDER BY ordinal_position
        """)
        existing = [row[0] for row in cursor.fetchall()]
        print(f"既存カラム: {existing}\n")
        
        # nameをproduct_nameに変更
        if 'name' in existing and 'product_name' not in existing:
            cursor.execute("ALTER TABLE products RENAME COLUMN name TO product_name")
            print("✅ name → product_name に変更")
        
        # 必要なカラムを追加
        columns = {
            'description': 'TEXT',
            'category': 'VARCHAR(50)',
            'stock_quantity': 'INTEGER DEFAULT 0',
            'image_data': 'TEXT',
            'is_active': 'BOOLEAN DEFAULT TRUE',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        print("カラムを追加中...")
        for col, typ in columns.items():
            if col not in existing:
                try:
                    cursor.execute(f"ALTER TABLE products ADD COLUMN {col} {typ}")
                    print(f"  ✅ {col} 追加")
                except Exception as e:
                    print(f"  ⚠️  {col} スキップ: {e}")
        
        conn.commit()
        print("\n=== 修正完了！ ===\n")
        
        # 結果確認
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'products' 
            ORDER BY ordinal_position
        """)
        print("最終的なカラム一覧:")
        for row in cursor.fetchall():
            print(f"  {row[0]:<20} ({row[1]})")
            
    except Exception as e:
        conn.rollback()
        print(f"\n❌ エラーが発生: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    fix_table()
EOF
