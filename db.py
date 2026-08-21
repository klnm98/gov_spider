"""
db.py —— 数据库层
职责：建表、查询已爬过的 URL、写入新数据。
把数据库操作独立出来，爬虫部分只负责调它，职责清晰、好复用。
"""
import sqlite3
class Database:
    def __init__(self, db_path: str, config: dict = None):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)   # SQLite 是零配置的文件数据库，一个文件存所有数据
        self.config = config
        self._create_table()
    def _create_table(self):
        """建表。url 加了 UNIQUE（唯一约束），这是去重的“第二道保险”。"""
        if self.config and 'table_structure' in self.config:
            table_config = self.config['table_structure']
            table_name = table_config.get('table_name', 'files')
            columns = table_config.get('columns', [])

            # 构建字段定义
            column_defs = []
            for col in columns:
                col_def = f"{col['name']} {col['type']}"
                if 'constraints' in col:
                    col_def += f" {col['constraints']}"
                if 'default' in col:
                    col_def += f" DEFAULT ({col['default']})"
                column_defs.append(col_def)

            # 生成建表 SQL
            sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n  "
            sql += ",\n  ".join(column_defs)
            sql += "\n)"
        else:
            # 默认表结构（向后兼容）
            sql = """
                CREATE TABLE IF NOT EXISTS files (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    title         TEXT,
                    url           TEXT UNIQUE,
                    publish_date  TEXT,
                    content       TEXT,
                    fetched_at    TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """

        self.conn.execute(sql)
        self.conn.commit()
    def get_existing_urls(self) -> set:
        """返回库里已有的所有 URL 集合。
        用于“增量判断”：爬之前先看看哪些已经爬过了，省网络请求。"""
        rows = self.conn.execute("SELECT url FROM files").fetchall()
        return {row[0] for row in rows}
    def insert_file(self, title, url, publish_date, content) -> int:
        """插入一条记录。
        INSERT OR IGNORE：如果 URL 已存在（唯一约束冲突）就直接忽略，不报错。
        返回值 = 1 表示真正插入；= 0 表示重复被跳过。"""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO files (title, url, publish_date, content) "
            "VALUES (?, ?, ?, ?)",
            (title, url, publish_date, content),
        )
        self.conn.commit()
        return cur.rowcount
    def close(self):
        self.conn.close()