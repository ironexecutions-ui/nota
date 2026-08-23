from datetime import datetime
from zoneinfo import ZoneInfo
import os
import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException

from database import conectar

from .nfce_xml import (
    gerar_xml_nfce,
    gerar_chave_acesso
)

from .pynfe_service import emitir_com_pynfe

from .nfce_validacoes import (
    validar_comercio_fiscal,
    validar_produto_fiscal
)


router = APIRouter()


# ==========================================================
# CONFIGURAÇÃO
# ==========================================================

FISCAL_API_TOKEN = "fiscal_secreto_2026"


# ==========================================================
# LOG
# ==========================================================

def log(msg):
    print(
        f"[NFCe][{datetime.now().strftime('%H:%M:%S')}] {msg}",
        flush=True
    )


# ==========================================================
# TOKEN DA API FISCAL
# ==========================================================

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


# ==========================================================
# GERAR QR CODE NFC-e
# ==========================================================

def gerar_qrcode_nfce(
    chave_acesso,
    ambiente,
    csc_id,
    csc_token
):

    log("========================================")
    log("GERANDO QR CODE NFC-e")
    log("========================================")

    chave_acesso = str(chave_acesso).strip()

    ambiente_normalizado = (
        str(ambiente)
        .strip()
        .lower()
    )

    csc_id = str(csc_id).strip()
    csc_token = str(csc_token).strip()

    # ------------------------------------------------------
    # AMBIENTE
    # ------------------------------------------------------

    if ambiente_normalizado == "homologacao":

        tp_amb = "2"

        url_consulta = (
            "https://www.homologacao.nfce.fazenda.sp.gov.br"
            "/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx"
        )

    elif ambiente_normalizado == "producao":

        tp_amb = "1"

        url_consulta = (
            "https://www.nfce.fazenda.sp.gov.br"
            "/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx"
        )

    else:

        raise Exception(
            f"Ambiente NFC-e inválido: {ambiente}"
        )

    # ------------------------------------------------------
    # CSC ID
    # ------------------------------------------------------

    if not csc_id.isdigit():
        raise Exception(
            f"CSC ID inválido: {csc_id}"
        )

    # SEFAZ trabalha com 6 posições
    csc_id_formatado = csc_id.zfill(6)

    # ------------------------------------------------------
    # QR CODE
    #
    # Formato utilizado neste fluxo:
    #
    # chave
    # versão
    # ambiente
    # identificador CSC
    #
    # O CSC é usado somente para gerar o SHA1.
    # Ele NÃO vai dentro da URL.
    # ------------------------------------------------------

    versao_qrcode = "2"

    parametros = (
        f"{chave_acesso}|"
        f"{versao_qrcode}|"
        f"{tp_amb}|"
        f"{csc_id_formatado}"
    )

    log(f"Chave QR Code: {chave_acesso}")
    log(f"Versão QR Code: {versao_qrcode}")
    log(f"tpAmb QR Code: {tp_amb}")
    log(f"CSC ID: {csc_id_formatado}")

    # ------------------------------------------------------
    # HASH
    # ------------------------------------------------------

    texto_hash = (
        parametros
        + csc_token
    )

    hash_qrcode = hashlib.sha1(
        texto_hash.encode("utf-8")
    ).hexdigest()

    log(
        f"Hash QR Code: {hash_qrcode}"
    )

    # ------------------------------------------------------
    # URL FINAL
    # ------------------------------------------------------

    parametros_finais = (
        f"{parametros}|"
        f"{hash_qrcode}"
    )

    qr_code_url = (
        f"{url_consulta}"
        f"?p={quote(parametros_finais, safe='|')}"
    )

    log(
        f"QR Code URL: {qr_code_url}"
    )

    log("QR Code gerado")

    return qr_code_url

def salvar_xml_nfce(
    xml_conteudo,
    comercio_id,
    ambiente,
    chave
):
    if not xml_conteudo:
        raise Exception(
            "XML autorizado não retornado pelo PyNFe"
        )

    agora = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    )

    pasta = os.path.join(
        "/var/www/nota/xml",
        str(comercio_id),
        str(ambiente).strip().lower(),
        agora.strftime("%Y"),
        agora.strftime("%m")
    )

    os.makedirs(
        pasta,
        exist_ok=True
    )

    caminho_xml = os.path.join(
        pasta,
        f"{chave}.xml"
    )

    if isinstance(xml_conteudo, str):
        xml_bytes = xml_conteudo.encode("utf-8")
    else:
        xml_bytes = xml_conteudo

    with open(caminho_xml, "wb") as arquivo:
        arquivo.write(xml_bytes)

    if not os.path.exists(caminho_xml):
        raise Exception(
            "Falha ao salvar XML autorizado da NFC-e"
        )

    log(
        f"XML autorizado salvo em: {caminho_xml}"
    )

    return caminho_xml
# ==========================================================
# EMITIR NFC-e
# ==========================================================

@router.post("/emitir/{venda_id}")
def emitir_nfce_manual(
    venda_id: int,
    authorization: str = Header(None)
):

    validar_token_fiscal(authorization)

    conn = conectar()

    cursor = conn.cursor(
        dictionary=True
    )

    tmp_path = None

    try:

        log("========================================")
        log("INICIANDO EMISSÃO NFC-e")
        log(f"Venda: {venda_id}")
        log("========================================")

        # ==================================================
        # 1. VENDA + COMÉRCIO + FISCAL
        # ==================================================

        cursor.execute(
            """
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
            """,
            (
                venda_id,
            )
        )

        dados = cursor.fetchone()

        if not dados:

            raise HTTPException(
                status_code=404,
                detail="Venda não encontrada"
            )

        log(
            f"Venda encontrada: {venda_id}"
        )

        comercio = dados
        fiscal = dados

        log(
            f"Comércio ID: {comercio['empresa']}"
        )

        log(
            f"Razão social: {fiscal.get('razao_social')}"
        )

        log(
            f"Ambiente: {fiscal.get('ambiente_emissao')}"
        )

        log(
            f"CSC ID: {fiscal.get('csc_id')}"
        )

        # NÃO LOGAR O TOKEN CSC

        validar_comercio_fiscal(
            fiscal
        )

        # ==================================================
        # 2. ITENS
        # ==================================================

        produtos_txt = dados.get(
            "produtos"
        )

        log(
            f"Produtos RAW da venda: {produtos_txt}"
        )

        if not produtos_txt:

            raise Exception(
                "Venda sem produtos"
            )

        itens = []

        lista_produtos = (
            produtos_txt.split(",")
        )

        for item_txt in lista_produtos:

            try:

                produto_id, quantidade = (
                    item_txt.split(":")
                )

            except Exception:

                log(
                    f"Formato inválido do item: {item_txt}"
                )

                continue

            produto_id = int(
                produto_id.strip()
            )

            quantidade = int(
                quantidade.strip()
            )

            log(
                f"Buscando produto {produto_id}"
            )

            cursor.execute(
                """
                SELECT

                    p.id,
                    p.nome,
                    p.preco,

                    f.ncm,
                    f.cfop,
                    f.origem,
                    f.cst_csosn,

                    f.cst_ibscbs,
                    f.cclass_trib,
                    f.aliquota_ibs_uf,
                    f.aliquota_ibs_mun,
                    f.aliquota_cbs

                FROM produtos_servicos p

                INNER JOIN fiscal_dados_cupons f
                    ON f.produto_id = p.id

                WHERE p.id = %s
                  AND f.comercio_id = %s

                LIMIT 1
                """,
                (
                    produto_id,
                    comercio["empresa"]
                )
            )

            produto = cursor.fetchone()

            if not produto:

                log(
                    f"PRODUTO SEM DADOS FISCAIS: {produto_id}"
                )

                continue

            produto["quantidade"] = (
                quantidade
            )

            produto["crt"] = str(
                fiscal["crt"]
            ).strip()

            log(
                f"CRT INJETADO NO PRODUTO: "
                f"{produto['crt']}"
            )

            log(
                f"Produto fiscal encontrado: "
                f"{produto['nome']}"
            )

            itens.append(
                produto
            )

        if not itens:

            raise Exception(
                "Venda sem itens fiscais"
            )

        log(
            f"Quantidade de itens fiscais: {len(itens)}"
        )

        # ==================================================
        # 3. VALIDAR PRODUTOS
        # ==================================================

        for item in itens:

            validar_produto_fiscal(
                item
            )

        total_nf = sum(
            item["quantidade"]
            * item["preco"]

            for item in itens
        )

        log(
            f"Total calculado NFC-e: {total_nf}"
        )

        # ==================================================
        # 4. NUMERAÇÃO
        # ==================================================

        cursor.execute(
            """
            SELECT ultimo_numero

            FROM fiscal_numeracao_nfce

            WHERE comercio_id = %s
              AND serie = %s
              AND ambiente = %s

            FOR UPDATE
            """,
            (
                comercio["empresa"],
                fiscal["serie_nfce"],
                fiscal["ambiente_emissao"]
            )
        )

        numeracao = (
            cursor.fetchone()
        )

        if not numeracao:

            raise Exception(
                "Numeração NFC-e não configurada"
            )

        numero_nfce = (
            int(numeracao["ultimo_numero"])
            + 1
        )

        log(
            f"Número NFC-e reservado: {numero_nfce}"
        )

        # ==================================================
        # 5. GERAR CHAVE
        # ==================================================

        agora_sp = datetime.now(
            ZoneInfo(
                "America/Sao_Paulo"
            )
        )

        ano_mes = agora_sp.strftime(
            "%y%m"
        )

        cnpj_limpo = (
            str(comercio["cnpj"])
            .replace(".", "")
            .replace("/", "")
            .replace("-", "")
            .strip()
        )

        codigo_uf = str(
            comercio["codigo_uf"]
        ).strip()

        chave_acesso, cNF, cDV = (
            gerar_chave_acesso(
                codigo_uf,
                ano_mes,
                cnpj_limpo,
                "65",
                fiscal["serie_nfce"],
                numero_nfce
            )
        )

        log(
            f"Chave de acesso: {chave_acesso}"
        )

        log(
            f"cNF: {cNF}"
        )

        log(
            f"cDV: {cDV}"
        )

        # ==================================================
        # 6. ATUALIZAR NUMERAÇÃO
        # ==================================================

        cursor.execute(
            """
            UPDATE fiscal_numeracao_nfce

            SET
                ultimo_numero = %s,
                atualizado_em = NOW()

            WHERE comercio_id = %s
              AND serie = %s
              AND ambiente = %s
            """,
            (
                numero_nfce,
                comercio["empresa"],
                fiscal["serie_nfce"],
                fiscal["ambiente_emissao"]
            )
        )

        # ==================================================
        # 7. GERAR QR CODE
        # ==================================================

        qr_code_url = gerar_qrcode_nfce(
            chave_acesso=chave_acesso,
            ambiente=fiscal[
                "ambiente_emissao"
            ],
            csc_id=fiscal[
                "csc_id"
            ],
            csc_token=fiscal[
                "csc_token"
            ]
        )

        # ==================================================
        # 8. MONTAR DADOS NFC-e
        # ==================================================

        dados_nfce = {

            "comercio": comercio,

            "fiscal": fiscal,

            "venda": dados,

            "itens": itens,

            "numero_nfce": numero_nfce,

            "chave_acesso": chave_acesso,

            "cNF": cNF,

            "cDV": cDV,

            "total_nf": total_nf,

            "data_emissao": agora_sp
        }

        # ==================================================
        # 9. GERAR XML COM QR CODE
        # ==================================================

        log(
            "Gerando XML NFC-e com QR Code..."
        )

        xml_base = gerar_xml_nfce(
            dados_nfce,
            qr_code_url
        )

        if xml_base is None:

            raise Exception(
                "gerar_xml_nfce retornou None"
            )

        log(
            "XML NFC-e gerado"
        )

        # ==================================================
        # 10. CERTIFICADO DO COMÉRCIO
        # ==================================================

        log(
            f"Carregando certificado do comércio "
            f"{comercio['empresa']}"
        )

        # ==================================================
        # PEGAR DADOS DO BANCO
        # ==================================================

        certificado_path = str(
            fiscal.get("certificado_path") or ""
        ).strip()

        certificado_senha_enc = str(
            fiscal.get("certificado_senha_enc") or ""
        ).strip()

        # ==================================================
        # VALIDAR DADOS
        # ==================================================

        if not certificado_path:

            raise Exception(
                "Certificado digital não configurado "
                f"para o comércio {comercio['empresa']}"
            )

        if not certificado_senha_enc:

            raise Exception(
                "Senha do certificado não configurada "
                f"para o comércio {comercio['empresa']}"
            )

        log(
            f"Certificado encontrado no banco: "
            f"{certificado_path}"
        )

        # ==================================================
        # SENHA DO CERTIFICADO
        # ==================================================
        
        senha_real = certificado_senha_enc
        
        log(
            "Senha do certificado carregada com sucesso"
        )

        # ==================================================
        # LOCALIZAR ARQUIVO PFX
        # ==================================================

        nome_certificado = (
            certificado_path
            .split("?")[0]
            .rstrip("/")
            .split("/")[-1]
        )

        if not nome_certificado:

            raise Exception(
                "Nome do certificado não encontrado"
            )

        if not nome_certificado.lower().endswith(".pfx"):

            raise Exception(
                "O certificado configurado não é um arquivo PFX"
            )

        tmp_path = os.path.abspath(
            os.path.join(
                "/var/www/iron-storage",
                nome_certificado
            )
        )

        log(
            f"Certificado físico: {tmp_path}"
        )

        # ==================================================
        # VALIDAR ARQUIVO
        # ==================================================

        if not os.path.exists(tmp_path):

            raise Exception(
                "Arquivo do certificado não encontrado "
                f"no servidor: {tmp_path}"
            )

        if not os.path.isfile(tmp_path):

            raise Exception(
                "O certificado configurado não é "
                "um arquivo válido"
            )

        log(
            f"Certificado do comércio "
            f"{comercio['empresa']} carregado com sucesso"
        )

        # ==================================================
        # 11. ASSINAR + ENVIAR
        # ==================================================

        log(
            "Enviando XML para PyNFe..."
        )


        retorno = emitir_com_pynfe(

            xml_base=xml_base,

            certificado_path=tmp_path,

            certificado_senha=senha_real,

            uf=comercio["estado"],

            homologacao=(
                str(
                    fiscal[
                        "ambiente_emissao"
                    ]
                )
                .strip()
                .lower()
                == "homologacao"
            )
        )

        log(
            f"Retorno PyNFe recebido: "
            f"cStat={retorno.get('cstat')}"
        )

        # ==================================================
        # 12. VALIDAR RETORNO
        # ==================================================

        if not retorno.get(
            "chave"
        ):

            raise Exception(
                "PyNFe não retornou "
                "chave da NFC-e"
            )

        if not retorno.get(
            "protocolo"
        ):

            raise Exception(
                "PyNFe não retornou "
                "protocolo da NFC-e"
            )

        qr_code_retorno = (
            retorno.get("qr_code")
            or qr_code_url
        )
        # ==================================================
        # 13. SALVAR XML AUTORIZADO
        # ==================================================

        xml_retorno = retorno.get(
            "xml_retorno"
        )

        if not xml_retorno:
            raise Exception(
                "PyNFe não retornou XML autorizado"
            )

        xml_path = salvar_xml_nfce(
            xml_conteudo=xml_retorno,
            comercio_id=comercio["empresa"],
            ambiente=fiscal["ambiente_emissao"],
            chave=retorno["chave"]
        )

        log(
            f"XML NFC-e armazenado em: {xml_path}"
        )
        # ==================================================
        # 13. REGISTRAR NFC-e
        # ==================================================

        # ==================================================
        # 14. REGISTRAR NFC-e
        # ==================================================

        cursor.execute(
            """
            INSERT INTO nfce_emitidas
            (
                comercio_id,
                venda_id,
                numero_nfce,
                serie,
                chave_acesso,
                xml_path,
                qr_code_url,
                protocolo_autorizacao,
                status,
                ambiente,
                criado_em
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                comercio["empresa"],
                venda_id,
                numero_nfce,
                fiscal["serie_nfce"],
                retorno["chave"],
                xml_path,
                qr_code_retorno,
                retorno["protocolo"],
                "autorizada",
                fiscal["ambiente_emissao"],
                agora_sp
            )
        )

        # ==================================================
        # 15. COMMIT
        # ==================================================

        conn.commit()

        log("========================================")
        log("NFC-e AUTORIZADA E SALVA")
        log(f"Número: {numero_nfce}")
        log(f"Chave: {retorno['chave']}")
        log(f"Protocolo: {retorno['protocolo']}")
        log(f"XML: {xml_path}")
        log("========================================")

        return {
            "ok": True,
            "venda_id": venda_id,
            "numero_nfce": numero_nfce,
            "chave": retorno["chave"],
            "protocolo": retorno["protocolo"],
            "qr_code": qr_code_retorno,
            "xml_path": xml_path,
            "cstat": retorno.get("cstat"),
            "motivo": retorno.get("motivo")
        }

    except HTTPException:

        conn.rollback()

        raise

    except Exception as e:

        conn.rollback()

        log("========================================")
        log("ERRO NA EMISSÃO NFC-e")
        log(str(e))
        log("========================================")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        try:
            cursor.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass
