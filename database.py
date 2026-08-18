import mysql.connector

# =========================
# CONTROLE DE CONEXÃO
# =========================
USAR_ONLINE = True   # True = banco online | False = banco local


# =========================
# CONFIGURAÇÕES
# =========================
CONFIG_LOCAL = {
    "host": "localhost",
    "user": "root",
    "password": "26374246",
    "database": "ironexecutions",
    "port": 3306
}

CONFIG_ONLINE = {
    "host": "sql5.freesqldatabase.com",
    "user": "sql5807683",
    "password": "RKCTBqiFvy",
    "database": "sql5807683",
    "port": 3306
}


# =========================
# CONEXÃO CENTRAL
# =========================
def conectar():
    config = CONFIG_ONLINE if USAR_ONLINE else CONFIG_LOCAL
    return mysql.connector.connect(**config)


# =========================
# HELPERS
# =========================
def executar_select(query, params=None):
    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(query, params or ())
    dados = cursor.fetchall()

    cursor.close()
    conn.close()
    return dados


def executar_comando(query, params=None):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(query, params or ())
    conn.commit()

    cursor.close()
    conn.close()


def executar_insert(query, params=None):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(query, params or ())
    conn.commit()

    row_id = cursor.lastrowid

    cursor.close()
    conn.close()
    return row_id


def obter_comercio_id_do_cliente(cliente_id: int):
    sql = """
        SELECT comercio_id
        FROM clientes
        WHERE id = %s
    """
    res = executar_select(sql, (cliente_id,))
    return res[0]["comercio_id"] if res else None
