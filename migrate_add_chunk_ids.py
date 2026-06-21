"""
Migration script to add vector_chunk_ids column to suggestion_history table.
Run this once to update existing database schema.
"""

import sqlite3
import os
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / 'data' / 'ayurveda.db'


def migrate():
    """Add vector_chunk_ids column if it doesn't exist."""
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        print("   No migration needed - schema will be created fresh when backend starts")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(suggestion_history)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'vector_chunk_ids' in columns:
            print("✅ Column 'vector_chunk_ids' already exists - no migration needed")
            return

        # Add the column
        print("📝 Adding 'vector_chunk_ids' column to suggestion_history table...")
        cursor.execute("""
            ALTER TABLE suggestion_history
            ADD COLUMN vector_chunk_ids TEXT NOT NULL DEFAULT '[]'
        """)

        conn.commit()
        print("✅ Migration completed successfully!")
        print("   Column 'vector_chunk_ids' added with default value '[]'")

    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    print("🔄 Running database migration...")
    print(f"   Database: {DB_PATH}")
    migrate()
