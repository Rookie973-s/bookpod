"""
Database driver selection.

On your own Windows PC the C-based `mysqlclient` is used. On the hosting server (Linux) it often
cannot be built, so `PyMySQL` (pure Python) is installed instead (see requirements.txt) and
is presented to Django as if it were mysqlclient.
"""
try:
    import MySQLdb  # noqa: F401  (mysqlclient is installed: nothing to do)
except ImportError:
    try:
        import pymysql
    except ImportError:  # SQLite mode or the driver is genuinely missing; Django will explain.
        pass
    else:
        # Django checks the driver version; PyMySQL 1.x speaks the same protocol as mysqlclient 2.2.
        pymysql.version_info = (2, 2, 1, "final", 0)
        pymysql.__version__ = "2.2.1"
        pymysql.install_as_MySQLdb()
