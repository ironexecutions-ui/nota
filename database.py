import os
import mysql.connector
from dotenv import load_dotenv

# =========================
# CARREGAR VARIÁVEIS .ENV
# =========================

load_dotenv()


# =========================
# CONFIGURAÇÃO DO BANCO
# =========================

CONFIG_BANCO = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": int(os.getenv("DB_PORT", "3306")),
}


# =========================
# CONEXÃO CENTRAL
# =========================

def conectar():
    return mysql.connector.connect(**CONFIG_BANCO)


# =========================
# HELPERS
# =========================

def executar_select(query, params=None):
    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(query, params or ())
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def executar_comando(query, params=None):
    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(query, params or ())
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def executar_insert(query, params=None):
    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(query, params or ())
        conn.commit()
        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def executar_update(query, params=None):
    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(query, params or ())
        conn.commit()
        return cursor.rowcount

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def obter_comercio_id_do_cliente(cliente_id: int):
    sql = """
        SELECT comercio_id
        FROM clientes
        WHERE id = %s
    """

    res = executar_select(sql, (cliente_id,))

    return res[0]["comercio_id"] if res else None
