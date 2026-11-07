from datetime import datetime
from zoneinfo import ZoneInfo
import os

from fastapi import APIRouter, Header, HTTPException, Body

from database import conectar

from .nfe_xml import gerar_xml_nfe
from .nfce_xml import gerar_chave_acesso
from .pynfe_service_nfe import emitir_com_pynfe
from .nfce_validacoes import validar_produto_fiscal
from .nfe_validacoes import validar_comercio_nfe
from .nfe_danfe import gerar_danfe_nfe


router = APIRouter(prefix="/nfe", tags=["NF-e"])
FISCAL_API_TOKEN = "fiscal_secreto_2026"


def log(msg):
    print(f"[NFe][{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def validar_token_fiscal(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token fiscal não informado")
    if authorization != f"Bearer {FISCAL_API_TOKEN}":
        raise HTTPException(status_code=403, detail="Token fiscal inválido")


def salvar_xml_nfe(xml_conteudo, comercio_id, ambiente, chave):
    if not xml_conteudo:
        raise Exception("XML autorizado não retornado pelo PyNFe")
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    pasta = os.path.join(
        "/var/www/nota/xml", str(comercio_id),
        str(ambiente).strip().lower(), agora.strftime("%Y"), agora.strftime("%m")
    )
    os.makedirs(pasta, exist_ok=True)
    caminho_xml = os.path.join(pasta, f"{chave}.xml")
    xml_bytes = xml_conteudo.encode("utf-8") if isinstance(xml_conteudo, str) else xml_conteudo
    with open(caminho_xml, "wb") as arquivo:
        arquivo.write(xml_bytes)
    if not os.path.isfile(caminho_xml):
        raise Exception("Falha ao salvar XML autorizado da NF-e")
    log(f"XML autorizado salvo em: {caminho_xml}")
    return caminho_xml


@router.post("/emitir/{venda_id}")
def emitir_nfe_manual(
    venda_id: int,
    payload: dict = Body(...),
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
        log("INICIANDO EMISSÃO NF-e")
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

        validar_comercio_nfe(
            fiscal
        )

        destinatario = payload.get("destinatario") or {}
        if not isinstance(destinatario, dict):
            raise Exception("Dados do destinatário da NF-e inválidos.")
        documento_dest = "".join(
            ch for ch in str(destinatario.get("documento") or "") if ch.isdigit()
        )
        if len(documento_dest) not in (11, 14):
            raise Exception("Destinatário precisa informar CPF ou CNPJ válido.")
        destinatario["documento"] = documento_dest

        # ==================================================
        # 2. ITENS
        # PRODUTOS NORMAIS + PRODUTOS POR PESO
        # ==================================================

        produtos_txt = dados.get("produtos")
        produtos_peso_txt = dados.get("produtos_peso")

        log(
            f"Produtos normais RAW da venda: "
            f"{produtos_txt}"
        )

        log(
            f"Produtos por peso RAW da venda: "
            f"{produtos_peso_txt}"
        )

        itens = []

        # ==================================================
        # FUNÇÃO INTERNA PARA BUSCAR DADOS FISCAIS
        # ==================================================

        def buscar_produto_fiscal(produto_id):

            log(
                f"Buscando dados fiscais do produto "
                f"{produto_id}"
            )

            cursor.execute(
                """
                SELECT

                    p.id,
                    p.nome,
                    p.preco,
                    p.peso,
                    p.unidade,

                    f.tipo,
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

                raise Exception(
                    f"Produto {produto_id} "
                    f"sem dados fiscais cadastrados"
                )

            produto["crt"] = str(
                fiscal["crt"]
            ).strip()

            return produto

        # ==================================================
        # 2.1 PRODUTOS NORMAIS
        # ==================================================

        if produtos_txt:

            lista_produtos = (
                produtos_txt.split(",")
            )

            for item_txt in lista_produtos:

                item_txt = (
                    str(item_txt)
                    .strip()
                )

                if not item_txt:
                    continue

                try:

                    produto_id_txt, quantidade_txt = (
                        item_txt.split(":", 1)
                    )

                    produto_id = int(
                        produto_id_txt.strip()
                    )

                    quantidade = float(
                        quantidade_txt.strip()
                    )

                except Exception:

                    log(
                        f"Formato inválido de produto "
                        f"normal: {item_txt}"
                    )

                    continue

                if quantidade <= 0:

                    log(
                        f"Quantidade inválida do produto "
                        f"{produto_id}: {quantidade}"
                    )

                    continue

                produto = buscar_produto_fiscal(
                    produto_id
                )

                # ==========================================
                # IMPORTANTE
                #
                # O campo "produtos" também contém o
                # produto por peso com quantidade 1.
                #
                # Como produtos_peso contém a informação
                # real desse item, ele NÃO pode entrar
                # novamente como produto normal.
                # ==========================================

                produto_esta_em_peso = False

                if produtos_peso_txt:

                    for peso_txt in (
                        produtos_peso_txt.split(",")
                    ):

                        try:

                            peso_id = int(
                                peso_txt
                                .split(":", 1)[0]
                                .strip()
                            )

                            if peso_id == produto_id:
                                produto_esta_em_peso = True
                                break

                        except Exception:
                            continue

                if produto_esta_em_peso:

                    log(
                        f"Produto {produto_id} está em "
                        f"produtos_peso. Ignorando versão "
                        f"normal para evitar duplicidade."
                    )

                    continue

                produto["quantidade"] = quantidade

                produto["eh_produto_peso"] = False

                produto["unidade_fiscal"] = (
                    str(
                        produto.get("unidade")
                        or "UN"
                    )
                    .strip()
                    .upper()
                )

                produto["valor_unitario_fiscal"] = float(
                    produto["preco"]
                )

                produto["valor_total_fiscal"] = round(
                    quantidade
                    * float(produto["preco"]),
                    2
                )

                log(
                    f"PRODUTO NORMAL | "
                    f"ID={produto_id} | "
                    f"Nome={produto['nome']} | "
                    f"Qtd={quantidade} | "
                    f"Preço={produto['preco']} | "
                    f"Total={produto['valor_total_fiscal']}"
                )

                itens.append(
                    produto
                )

        # ==================================================
        # 2.2 PRODUTOS POR PESO
        #
        # Formato salvo:
        #
        # produto_id:gramas:valor_cobrado
        #
        # Exemplo:
        #
        # 15:350:4.20
        #
        # Para NF-e vamos trabalhar em KG.
        #
        # 350g = 0.3500 KG
        #
        # O preço unitário fiscal é calculado para que:
        #
        # qCom * vUnCom = valor realmente cobrado
        # ==================================================

        if produtos_peso_txt:

            lista_produtos_peso = (
                produtos_peso_txt.split(",")
            )

            for item_txt in lista_produtos_peso:

                item_txt = (
                    str(item_txt)
                    .strip()
                )

                if not item_txt:
                    continue

                try:

                    partes = item_txt.split(":")

                    if len(partes) != 3:

                        raise ValueError(
                            "Produto por peso deve possuir "
                            "id:gramas:valor"
                        )

                    produto_id = int(
                        partes[0].strip()
                    )

                    gramas = float(
                        partes[1].strip()
                    )

                    valor_cobrado = float(
                        partes[2].strip()
                    )

                except Exception as erro:

                    log(
                        f"Formato inválido de produto "
                        f"por peso: {item_txt} | "
                        f"Erro: {erro}"
                    )

                    continue

                if gramas <= 0:

                    log(
                        f"Peso inválido no produto "
                        f"{produto_id}: {gramas}g"
                    )

                    continue

                if valor_cobrado < 0:

                    log(
                        f"Valor inválido no produto "
                        f"{produto_id}: "
                        f"R$ {valor_cobrado}"
                    )

                    continue

                produto = buscar_produto_fiscal(
                    produto_id
                )

                # ==========================================
                # CONVERTER GRAMAS PARA KG
                # ==========================================

                quantidade_kg = (
                    gramas / 1000
                )

                if quantidade_kg <= 0:

                    raise Exception(
                        f"Quantidade em KG inválida "
                        f"para produto {produto_id}"
                    )

                # ==========================================
                # PREÇO POR KG DAQUELA VENDA
                #
                # Usamos o valor efetivamente cobrado.
                #
                # Exemplo:
                #
                # 350g
                # R$ 4,20
                #
                # 0.350 KG
                # R$ 12,00/KG
                # ==========================================

                valor_unitario_kg = (
                    valor_cobrado
                    / quantidade_kg
                )

                produto["eh_produto_peso"] = True

                produto["gramas"] = gramas

                produto["quantidade"] = quantidade_kg

                produto["unidade_fiscal"] = "KG"

                produto["valor_unitario_fiscal"] = (
                    valor_unitario_kg
                )

                produto["valor_total_fiscal"] = round(
                    valor_cobrado,
                    2
                )

                log(
                    f"PRODUTO POR PESO | "
                    f"ID={produto_id} | "
                    f"Nome={produto['nome']} | "
                    f"Peso={gramas}g | "
                    f"qCom={quantidade_kg:.4f} KG | "
                    f"vUnCom={valor_unitario_kg:.10f} | "
                    f"vProd={valor_cobrado:.2f}"
                )

                itens.append(
                    produto
                )

        # ==================================================
        # GARANTIR QUE EXISTEM ITENS
        # ==================================================

        if not itens:

            raise Exception(
                "Venda sem itens fiscais"
            )

        log(
            f"Quantidade de itens fiscais: "
            f"{len(itens)}"
        )

        quantidade_normais = sum(
            1
            for item in itens
            if not item.get(
                "eh_produto_peso"
            )
        )

        quantidade_peso = sum(
            1
            for item in itens
            if item.get(
                "eh_produto_peso"
            )
        )

        log(
            f"Itens normais: "
            f"{quantidade_normais}"
        )

        log(
            f"Itens por peso: "
            f"{quantidade_peso}"
        )
        # ==================================================
        # 3. VALIDAR PRODUTOS
        # ==================================================

        for item in itens:

            validar_produto_fiscal(
                item
            )

        # ==================================================
        # TOTAL DA NF-e
        #
        # Produto normal usa o total calculado normalmente.
        # Produto por peso usa exatamente o valor cobrado.
        # ==================================================

        total_nf = round(
            sum(
                float(
                    item["valor_total_fiscal"]
                )
                for item in itens
            ),
            2
        )

        log(
            f"Total calculado NF-e: "
            f"{total_nf:.2f}"
        )

        log(
            f"Valor pago da venda: "
            f"{float(dados.get('valor_pago') or 0):.2f}"
        )

        # ==================================================
        # 4. NUMERAÇÃO
        # ==================================================


        cursor.execute(
            """
            SELECT ultimo_numero

            FROM fiscal_numeracao_nfe

            WHERE comercio_id = %s
              AND serie = %s
              AND ambiente = %s

            FOR UPDATE
            """,
            (
                comercio["empresa"],
                fiscal["serie_nfe"],
                fiscal["ambiente_emissao"]
            )
        )

        numeracao = (
            cursor.fetchone()
        )

        # A numeração fica bloqueada nesta transação. Revalidamos a venda
        # depois do FOR UPDATE para impedir duas emissões simultâneas.
        cursor.execute(
            """
            SELECT id, numero_nfe, chave_acesso, protocolo_autorizacao
            FROM nfe_emitidas
            WHERE comercio_id = %s
              AND venda_id = %s
              AND ambiente = %s
              AND status = 'autorizada'
            LIMIT 1
            """,
            (
                comercio["empresa"],
                venda_id,
                fiscal["ambiente_emissao"]
            )
        )
        nfe_existente = cursor.fetchone()

        if nfe_existente:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensagem": "Esta venda já possui uma NF-e autorizada.",
                    "numero_nfe": nfe_existente["numero_nfe"],
                    "chave": nfe_existente["chave_acesso"],
                    "protocolo": nfe_existente["protocolo_autorizacao"]
                }
            )

        if not numeracao:

            raise Exception(
                "Numeração NF-e não configurada"
            )

        numero_nfe = (
            int(numeracao["ultimo_numero"])
            + 1
        )

        log(
            f"Número NF-e reservado: {numero_nfe}"
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
                "55",
                fiscal["serie_nfe"],
                numero_nfe
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
            UPDATE fiscal_numeracao_nfe

            SET
                ultimo_numero = %s,
                atualizado_em = NOW()

            WHERE comercio_id = %s
              AND serie = %s
              AND ambiente = %s
            """,
            (
                numero_nfe,
                comercio["empresa"],
                fiscal["serie_nfe"],
                fiscal["ambiente_emissao"]
            )
        )

        # ==================================================
        # 8. MONTAR DADOS NF-e
        # ==================================================

        uf_dest = str(destinatario.get("uf") or "").strip().upper()
        uf_emit = str(comercio.get("estado") or "").strip().upper()

        dados_nfe = {
            "comercio": comercio,
            "fiscal": fiscal,
            "venda": dados,
            "itens": itens,
            "numero_nfe": numero_nfe,
            "chave_acesso": chave_acesso,
            "cNF": cNF,
            "cDV": cDV,
            "total_nf": total_nf,
            "data_emissao": agora_sp,
            "destinatario": destinatario,
            "id_dest": "1" if uf_dest == uf_emit else "2",
            "ind_pres": str(payload.get("ind_pres") or "9"),
            "natureza_operacao": payload.get("natureza_operacao") or "VENDA DE MERCADORIA"
        }

        # ==================================================
        # 9. GERAR XML NF-e
        # ==================================================

        log("Gerando XML NF-e modelo 55...")

        xml_base = gerar_xml_nfe(dados_nfe)

        if xml_base is None:

            raise Exception(
                "gerar_xml_nfe retornou None"
            )

        log(
            "XML NF-e gerado"
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
            ),
            modelo="nfe"
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
                "chave da NF-e"
            )

        if not retorno.get(
            "protocolo"
        ):

            raise Exception(
                "PyNFe não retornou "
                "protocolo da NF-e"
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

        xml_path = salvar_xml_nfe(
            xml_conteudo=xml_retorno,
            comercio_id=comercio["empresa"],
            ambiente=fiscal["ambiente_emissao"],
            chave=retorno["chave"]
        )

        log(f"XML NF-e armazenado em: {xml_path}")

        pasta_danfe = os.path.join(
            "/var/www/nota/danfe",
            str(comercio["empresa"]),
            str(fiscal["ambiente_emissao"]).strip().lower(),
            agora_sp.strftime("%Y"),
            agora_sp.strftime("%m")
        )
        os.makedirs(pasta_danfe, exist_ok=True)
        danfe_path = os.path.join(pasta_danfe, f"{retorno['chave']}.pdf")

        gerar_danfe_nfe(
            dados=dados_nfe,
            chave=retorno["chave"],
            protocolo=retorno["protocolo"],
            caminho_saida=danfe_path
        )

        # ==================================================
        # REGISTRAR NF-e
        # ==================================================

        # ==================================================
        # 14. REGISTRAR NF-e
        # ==================================================

        cursor.execute(
            """
            INSERT INTO nfe_emitidas
            (
                comercio_id, venda_id, numero_nfe, serie,
                chave_acesso, xml_path, protocolo_autorizacao,
                status, ambiente, criado_em
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                comercio["empresa"],
                venda_id,
                numero_nfe,
                fiscal["serie_nfe"],
                retorno["chave"],
                xml_path,
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
        log("NF-e AUTORIZADA E SALVA")
        log(f"Número: {numero_nfe}")
        log(f"Chave: {retorno['chave']}")
        log(f"Protocolo: {retorno['protocolo']}")
        log(f"XML: {xml_path}")
        log("========================================")

        return {
            "ok": True,
            "venda_id": venda_id,
            "numero_nfe": numero_nfe,
            "chave": retorno["chave"],
            "protocolo": retorno["protocolo"],
            "xml_path": xml_path,
            "danfe_path": danfe_path,
            "cstat": retorno.get("cstat"),
            "motivo": retorno.get("motivo")
        }

    except HTTPException:

        conn.rollback()

        raise

    except Exception as e:

        conn.rollback()

        log("========================================")
        log("ERRO NA EMISSÃO NF-e")
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
