import os
import mysql.connector

from dotenv import load_dotenv


# =========================
# CARREGAR .ENV
# =========================

load_dotenv()


# esse aqui é da notas fiscais

# =========================
# CONTROLE DE CONEXÃO
# =========================

USAR_ONLINE = True  # True = banco online | False = banco local


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
    config = CONFIG_ONLINE if USAR_ONLINE else CONFIG_LOCAL
    return mysql.connector.connect(**config)
