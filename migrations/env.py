# migrations/env.py
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 這是 Alembic 在運行遷移時讀取您資料庫模型的關鍵
# 從 app.py 導入您的 Flask 應用程式和 db 物件
# 關鍵：確保這裡能找到 app 和 db
from app import app, db


# 這會指向 SQLAlchemy 的 MetaData 物件
# 關鍵：將 target_metadata 設定為 db.metadata
target_metadata = db.metadata

# 加載 .env 檔案中的環境變數
from dotenv import load_dotenv
load_dotenv()


# 這個區塊通常保持不變
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import Base
# target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is still acceptable
    here.  By skipping the Engine creation we don't even need
    a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = os.environ.get("DATABASE_URL") # 確保這裡從環境變數獲取
    if url is None:
        url = config.get_main_option("sqlalchemy.url") # 如果環境變數沒有，則嘗試從 ini 檔案獲取
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 關鍵：在 Flask 應用程式上下文中運行，這樣 db 物件才能被正確初始化
    with app.app_context():
        connectable = db.engine

        if connectable.url.drivername == 'postgresql':
            # 處理 psycopg2 驅動的參數，如果需要
            pass

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                # 這裡可以添加其他配置，例如 op.batch_alter_table for SQLite in-place ALTER
                # include_object=include_object,
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()