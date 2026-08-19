from datetime import datetime
import tempfile
from zoneinfo import ZoneInfo
import os

from fastapi import APIRouter, Header, HTTPException

from fiscal.database import conectar
from .nfce_xml import gerar_xml_nfce
from .nfce_assinatura import assinar_xml
from .nfce_envio import enviar_nfce
from .nfce_validacoes import (
    validar_comercio_fiscal,
    validar_produto_fiscal
)
from .nfce_xml import gerar_chave_acesso

router = APIRouter()

FISCAL_API_TOKEN = "fiscal_secreto_2026"


def validar_token_fiscal(authorization: str):

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Token fiscal não informado"
        )

    if authorization != f"Bearer {FISCAL_API_TOKEN}":
        raise HTTPException(
            status_code=403,
            detail="Token fiscal inválido"
        )


def log(msg):
    print(f"[NFCe][{datetime.now().strftime('%H:%M:%S')}] {msg}")


@router.post("/emitir/{venda_id}")
def emitir_nfce_manual(
    venda_id: int,
    authorization: str = Header(None)
):

    validar_token_fiscal(authorization)

    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    tmp_path = None

    try:

        # ===============================
        # 1. VENDA + COMÉRCIO + FISCAL
        # ===============================
        cursor.execute("""
            SELECT 
                v.*,
                c.*,
                f.*
            FROM vendas_ib v
            INNER JOIN comercios_cadastradas c
                ON c.id = v.empresa
            INNER JOIN fiscal_dados_comercio f
                ON f.comercio_id = c.id
            WHERE v.id = %s
        """, (venda_id,))

        dados = cursor.fetchone()

        if not dados:
            raise HTTPException(
                status_code=404,
                detail="Venda não encontrada"
            )

        log(f"Venda encontrada: {venda_id}")

        comercio = dados
        fiscal = dados

        validar_comercio_fiscal(fiscal)

        # ===============================
        # 2. ITENS
        # ===============================
        produtos_txt = dados.get("produtos")

        log(f"Produtos RAW da venda: {produtos_txt}")

        if not produtos_txt:
            raise Exception("Venda sem produtos")

        itens = []

        lista_produtos = produtos_txt.split(",")

        for item_txt in lista_produtos:

            try:
                produto_id, quantidade = item_txt.split(":")
            except Exception:
                log(f"Formato inválido do item: {item_txt}")
                continue

            log(f"Buscando produto {produto_id}")

            cursor.execute("""
                SELECT
                    p.id,
                    p.nome,
                    p.preco,
                    f.ncm,
                    f.cfop,
                    f.origem,
                    f.cst_csosn
                FROM produtos_servicos p
                INNER JOIN fiscal_dados_cupons f
                    ON f.produto_id = p.id
                WHERE p.id = %s
                  AND f.comercio_id = %s
                LIMIT 1
            """, (
                int(produto_id),
                comercio["empresa"]
            ))

            produto = cursor.fetchone()

            if not produto:
                log(f"PRODUTO SEM DADOS FISCAIS: {produto_id}")
                continue

            produto["quantidade"] = int(quantidade)

            produto["crt"] = str(fiscal["crt"]).strip()

            log(f"CRT INJETADO NO PRODUTO: {produto['crt']}")

            log(f"Produto fiscal encontrado: {produto['nome']}")

            itens.append(produto)

        if not itens:
            raise Exception("Venda sem itens fiscais")

        # ===============================
        # VALIDA PRODUTOS
        # ===============================
        for item in itens:
            validar_produto_fiscal(item)

        total_nf = sum(
            i["quantidade"] * i["preco"]
            for i in itens
        )

        # ===============================
        # 3. NUMERAÇÃO
        # ===============================
        cursor.execute("""
            SELECT ultimo_numero
            FROM fiscal_numeracao_nfce
            WHERE comercio_id = %s
              AND serie = %s
              AND ambiente = %s
            FOR UPDATE
        """, (
            comercio["empresa"],
            fiscal["serie_nfce"],
            fiscal["ambiente_emissao"]
        ))

        numeracao = cursor.fetchone()

        if not numeracao:
            raise Exception(
                "Numeração NFC-e não configurada"
            )

        numero_nfce = numeracao["ultimo_numero"] + 1

        # ===============================
        # GERAR CHAVE
        # ===============================
        ano_mes = datetime.now().strftime("%y%m")

        cnpj_limpo = (
            comercio["cnpj"]
            .replace(".", "")
            .replace("/", "")
            .replace("-", "")
        )

        codigo_uf = comercio["codigo_uf"]

        chave_acesso, cNF, cDV = gerar_chave_acesso(
            codigo_uf,
            ano_mes,
            cnpj_limpo,
            "65",
            fiscal["serie_nfce"],
            numero_nfce
        )

        # ===============================
        # ATUALIZA NUMERAÇÃO
        # ===============================
        cursor.execute("""
            UPDATE fiscal_numeracao_nfce
            SET ultimo_numero = %s,
                atualizado_em = NOW()
            WHERE comercio_id = %s
              AND serie = %s
              AND ambiente = %s
        """, (
            numero_nfce,
            comercio["empresa"],
            fiscal["serie_nfce"],
            fiscal["ambiente_emissao"]
        ))

        # ===============================
        # 4. XML
        # ===============================
        dados_nfce = {
            "comercio": comercio,
            "fiscal": fiscal,
            "venda": dados,
            "itens": itens,
            "numero_nfce": numero_nfce,
            "chave_acesso": chave_acesso,
            "cNF": cNF,
            "cDV": cDV
        }

        xml_base = gerar_xml_nfce(
            dados_nfce,
            None
        )

        # ===============================
        # CERTIFICADO LOCAL
        # ===============================
        if comercio["empresa"] != 25:
            raise Exception(
                "Certificado não configurado para este comércio"
            )

        BASE_DIR = os.path.dirname(
            os.path.abspath(__file__)
        )

        tmp_path = os.path.join(
            BASE_DIR,
            "certificado",
            "enya.pfx"
        )
        tmp_path = os.path.abspath(tmp_path)

        log(f"Certificado localizado em: {tmp_path}")

        if not os.path.exists(tmp_path):
            raise Exception(
                "Arquivo do certificado não encontrado"
            )

        senha_real = "12345678"

        # ===============================
        # ASSINAR XML
        # ===============================
        xml_assinado = assinar_xml(
            xml_base,
            tmp_path,
            senha_real
        )

        # ===============================
        # ENVIAR NFC-e
        # ===============================
        retorno = enviar_nfce(
            xml_assinado,
            fiscal["ambiente_emissao"],
            tmp_path,
            senha_real,
            fiscal,
            total_nf
        )

        # ===============================
        # 5. REGISTRAR NFC-e
        # ===============================
        cursor.execute("""
            INSERT INTO nfce_emitidas
            (
                comercio_id,
                venda_id,
                numero_nfce,
                serie,
                chave_acesso,
                qr_code_url,
                protocolo_autorizacao,
                status,
                ambiente,
                criado_em
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            comercio["empresa"],
            venda_id,
            numero_nfce,
            fiscal["serie_nfce"],
            retorno["chave"],
            retorno["qr_code"],
            retorno["protocolo"],
            "autorizada",
            fiscal["ambiente_emissao"],
            datetime.now(
                ZoneInfo("America/Sao_Paulo")
            )
        ))

        conn.commit()

        return {
            "ok": True,
            "venda_id": venda_id,
            "numero_nfce": numero_nfce,
            "chave": retorno["chave"]
        }

    except Exception as e:

        conn.rollback()

        log(str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()