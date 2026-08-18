from lxml import etree
from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import re
import random


# ==========================================
# LIMPEZA
# ==========================================
def somente_numeros(valor):

    if valor is None:
        return ""

    return re.sub(r"\D", "", str(valor))


def limpar_texto_xml(texto):

    if texto is None:
        return ""

    texto = str(texto).strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto
    ).encode(
        "ASCII",
        "ignore"
    ).decode(
        "ASCII"
    )

    return texto.upper()


# ==========================================
# PAGAMENTO
# ==========================================
def mapear_tpag(pagamento):

    if pagamento is None:
        return "99"

    pagamento = str(pagamento).strip().lower()

    mapa = {
        "dinheiro": "01",

        "cheque": "02",

        "credito": "03",
        "crédito": "03",
        "cartao_credito": "03",
        "cartão_credito": "03",

        "debito": "04",
        "débito": "04",
        "cartao_debito": "04",
        "cartão_debito": "04",

        "pix": "17",

        "outros": "99",
        "outro": "99"
    }

    return mapa.get(pagamento, "99")


# ==========================================
# ICMS
# ==========================================
def gerar_icms(imposto, item, origem, cst_csosn):

    icms = etree.SubElement(
        imposto,
        "ICMS"
    )

    crt = str(
        item.get("crt", "")
    ).strip()

    codigo = somente_numeros(
        cst_csosn
    )

    # ==========================================
    # SIMPLES NACIONAL
    # ==========================================
    if crt == "1":

        # ==========================================
        # CSOSN 102, 103, 300 e 400
        # ==========================================
        if codigo in [
            "102",
            "103",
            "300",
            "400"
        ]:

            grupo = etree.SubElement(
                icms,
                "ICMSSN102"
            )

            etree.SubElement(
                grupo,
                "orig"
            ).text = origem

            etree.SubElement(
                grupo,
                "CSOSN"
            ).text = codigo

            return

        # ==========================================
        # CSOSN 500
        # ==========================================
        if codigo == "500":

            grupo = etree.SubElement(
                icms,
                "ICMSSN500"
            )

            etree.SubElement(
                grupo,
                "orig"
            ).text = origem

            etree.SubElement(
                grupo,
                "CSOSN"
            ).text = codigo

            return

        raise Exception(
            f"CSOSN {codigo} ainda não implementado "
            f"para o produto {item.get('id')}"
        )

    # ==========================================
    # REGIME NORMAL
    # ==========================================
    if crt in ["2", "3"]:

        # ==========================================
        # CST 00
        # ==========================================
        if codigo == "00":

            grupo = etree.SubElement(
                icms,
                "ICMS00"
            )

            etree.SubElement(
                grupo,
                "orig"
            ).text = origem

            etree.SubElement(
                grupo,
                "CST"
            ).text = codigo

            etree.SubElement(
                grupo,
                "modBC"
            ).text = "3"

            etree.SubElement(
                grupo,
                "vBC"
            ).text = "0.00"

            etree.SubElement(
                grupo,
                "pICMS"
            ).text = "0.00"

            etree.SubElement(
                grupo,
                "vICMS"
            ).text = "0.00"

            return

        # ==========================================
        # CST 40, 41 e 50
        # ==========================================
        if codigo in [
            "40",
            "41",
            "50"
        ]:

            grupo = etree.SubElement(
                icms,
                "ICMS40"
            )

            etree.SubElement(
                grupo,
                "orig"
            ).text = origem

            etree.SubElement(
                grupo,
                "CST"
            ).text = codigo

            return

        raise Exception(
            f"CST {codigo} ainda não implementado "
            f"para o produto {item.get('id')}"
        )

    raise Exception(
        f"CRT {crt} inválido ou não suportado"
    )


# ==========================================
# XML NFC-e
# ==========================================
def gerar_xml_nfce(dados, qr_code_url):

    comercio = dados["comercio"]
    fiscal = dados["fiscal"]
    itens = dados["itens"]
    venda = dados["venda"]
    numero_nfce = dados["numero_nfce"]

    chave_acesso = dados["chave_acesso"]
    cNF = dados["cNF"]
    cDV = dados["cDV"]

    # ==========================================
    # LIMPEZA FISCAL
    # ==========================================
    cnpj = somente_numeros(
        comercio["cnpj"]
    )

    ie = somente_numeros(
        fiscal["inscricao_estadual"]
    )

    cep = somente_numeros(
        comercio["cep"]
    )

    cidade = limpar_texto_xml(
        comercio["cidade"]
    )

    estado = limpar_texto_xml(
        comercio["estado"]
    )

    razao_social = limpar_texto_xml(
        fiscal["razao_social"]
    )

    rua = limpar_texto_xml(
        comercio["rua"]
    )

    bairro = limpar_texto_xml(
        comercio["bairro"]
    )

    numero_endereco = str(
        comercio["numero"]
    ).strip()

    telefone = somente_numeros(
        comercio.get("telefone", "")
    )

    # ==========================================
    # XML BASE
    # ==========================================
    NFE = "http://www.portalfiscal.inf.br/nfe"

    nsmap = {
        None: NFE
    }

    nfe = etree.Element(
        "NFe",
        nsmap=nsmap
    )

    infNFe = etree.SubElement(
        nfe,
        "infNFe",
        Id=f"NFe{chave_acesso}",
        versao="4.00"
    )

    # ==========================================
    # IDE
    # ==========================================
    ide = etree.SubElement(
        infNFe,
        "ide"
    )

    etree.SubElement(
        ide,
        "cUF"
    ).text = chave_acesso[:2]

    etree.SubElement(
        ide,
        "cNF"
    ).text = cNF

    etree.SubElement(
        ide,
        "natOp"
    ).text = "VENDA DE MERCADORIA"

    etree.SubElement(
        ide,
        "mod"
    ).text = "65"

    etree.SubElement(
        ide,
        "serie"
    ).text = str(
        fiscal["serie_nfce"]
    )

    etree.SubElement(
        ide,
        "nNF"
    ).text = str(
        numero_nfce
    )

    dh_emi = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).replace(
        microsecond=0
    ).isoformat()

    etree.SubElement(
        ide,
        "dhEmi"
    ).text = dh_emi

    etree.SubElement(
        ide,
        "tpNF"
    ).text = "1"

    etree.SubElement(
        ide,
        "idDest"
    ).text = "1"

    etree.SubElement(
        ide,
        "cMunFG"
    ).text = somente_numeros(
        comercio["codigo_municipio"]
    )

    etree.SubElement(
        ide,
        "tpImp"
    ).text = "4"

    etree.SubElement(
        ide,
        "tpEmis"
    ).text = "1"

    etree.SubElement(
        ide,
        "cDV"
    ).text = cDV

    etree.SubElement(
        ide,
        "tpAmb"
    ).text = (
        "2"
        if fiscal["ambiente_emissao"] == "homologacao"
        else "1"
    )

    etree.SubElement(
        ide,
        "finNFe"
    ).text = "1"

    etree.SubElement(
        ide,
        "indFinal"
    ).text = "1"

    etree.SubElement(
        ide,
        "indPres"
    ).text = "1"

    etree.SubElement(
        ide,
        "procEmi"
    ).text = "0"

    etree.SubElement(
        ide,
        "verProc"
    ).text = "IRON1"

    # ==========================================
    # EMITENTE
    # ==========================================
    emit = etree.SubElement(
        infNFe,
        "emit"
    )

    etree.SubElement(
        emit,
        "CNPJ"
    ).text = cnpj

    etree.SubElement(
        emit,
        "xNome"
    ).text = razao_social

    etree.SubElement(
        emit,
        "xFant"
    ).text = razao_social

    ender = etree.SubElement(
        emit,
        "enderEmit"
    )

    etree.SubElement(
        ender,
        "xLgr"
    ).text = rua

    etree.SubElement(
        ender,
        "nro"
    ).text = numero_endereco

    etree.SubElement(
        ender,
        "xBairro"
    ).text = bairro

    etree.SubElement(
        ender,
        "cMun"
    ).text = somente_numeros(
        comercio["codigo_municipio"]
    )

    etree.SubElement(
        ender,
        "xMun"
    ).text = cidade

    etree.SubElement(
        ender,
        "UF"
    ).text = estado

    etree.SubElement(
        ender,
        "CEP"
    ).text = cep

    etree.SubElement(
        ender,
        "cPais"
    ).text = "1058"

    etree.SubElement(
        ender,
        "xPais"
    ).text = "BRASIL"

    if telefone:

        etree.SubElement(
            ender,
            "fone"
        ).text = telefone

    etree.SubElement(
        emit,
        "IE"
    ).text = ie

    etree.SubElement(
        emit,
        "CRT"
    ).text = str(
        fiscal["crt"]
    )

    # ==========================================
    # DESTINATÁRIO
    # ==========================================
    cpf = somente_numeros(
        venda.get("cpf_consumidor")
    )

    if cpf:

        dest = etree.SubElement(
            infNFe,
            "dest"
        )

        etree.SubElement(
            dest,
            "CPF"
        ).text = cpf

        etree.SubElement(
            dest,
            "indIEDest"
        ).text = "9"

    # ==========================================
    # PRODUTOS
    # ==========================================
    total_produtos = 0

    for idx, item in enumerate(
        itens,
        start=1
    ):

        det = etree.SubElement(
            infNFe,
            "det",
            nItem=str(idx)
        )

        prod = etree.SubElement(
            det,
            "prod"
        )

        nome_produto = limpar_texto_xml(
            item["nome"]
        )

        ncm = somente_numeros(
            item["ncm"]
        )

        cfop = somente_numeros(
            item["cfop"]
        )

        origem = somente_numeros(
            item["origem"]
        )

        cst_csosn = somente_numeros(
            item["cst_csosn"]
        )

        quantidade = float(
            item["quantidade"]
        )

        preco = float(
            item["preco"]
        )

        etree.SubElement(
            prod,
            "cProd"
        ).text = str(
            item["id"]
        )

        etree.SubElement(
            prod,
            "cEAN"
        ).text = "SEM GTIN"

        etree.SubElement(
            prod,
            "xProd"
        ).text = nome_produto

        etree.SubElement(
            prod,
            "NCM"
        ).text = ncm

        etree.SubElement(
            prod,
            "CFOP"
        ).text = cfop

        etree.SubElement(
            prod,
            "uCom"
        ).text = "UN"

        etree.SubElement(
            prod,
            "qCom"
        ).text = f"{quantidade:.4f}"

        etree.SubElement(
            prod,
            "vUnCom"
        ).text = f"{preco:.4f}"

        v_prod = (
            quantidade *
            preco
        )

        etree.SubElement(
            prod,
            "vProd"
        ).text = f"{v_prod:.2f}"

        etree.SubElement(
            prod,
            "cEANTrib"
        ).text = "SEM GTIN"

        etree.SubElement(
            prod,
            "uTrib"
        ).text = "UN"

        etree.SubElement(
            prod,
            "qTrib"
        ).text = f"{quantidade:.4f}"

        etree.SubElement(
            prod,
            "vUnTrib"
        ).text = f"{preco:.4f}"

        etree.SubElement(
            prod,
            "indTot"
        ).text = "1"

        total_produtos += v_prod

        # ==========================================
        # IMPOSTOS
        # ==========================================
        imposto = etree.SubElement(
            det,
            "imposto"
        )

        etree.SubElement(
            imposto,
            "vTotTrib"
        ).text = "0.00"

        # ==========================================
        # ICMS
        # ==========================================
        gerar_icms(
            imposto,
            item,
            origem,
            cst_csosn
        )

        # ==========================================
        # PIS
        # ==========================================
        pis = etree.SubElement(
            imposto,
            "PIS"
        )

        pis_nt = etree.SubElement(
            pis,
            "PISNT"
        )

        etree.SubElement(
            pis_nt,
            "CST"
        ).text = "08"

        # ==========================================
        # COFINS
        # ==========================================
        cofins = etree.SubElement(
            imposto,
            "COFINS"
        )

        cofins_nt = etree.SubElement(
            cofins,
            "COFINSNT"
        )

        etree.SubElement(
            cofins_nt,
            "CST"
        ).text = "08"

    # ==========================================
    # TOTAL
    # ==========================================
    total = etree.SubElement(
        infNFe,
        "total"
    )

    icmsTot = etree.SubElement(
        total,
        "ICMSTot"
    )

    campos_total = {

        "vBC": "0.00",

        "vICMS": "0.00",

        "vICMSDeson": "0.00",

        "vFCP": "0.00",

        "vBCST": "0.00",

        "vST": "0.00",

        "vProd": f"{total_produtos:.2f}",

        "vFrete": "0.00",

        "vSeg": "0.00",

        "vDesc": "0.00",

        "vII": "0.00",

        "vIPI": "0.00",

        "vPIS": "0.00",

        "vCOFINS": "0.00",

        "vOutro": "0.00",

        "vTotTrib": "0.00",

        "vNF": f"{total_produtos:.2f}"
    }

    for tag, valor in campos_total.items():

        etree.SubElement(
            icmsTot,
            tag
        ).text = valor

    # ==========================================
    # TRANSPORTE
    # ==========================================
    transp = etree.SubElement(
        infNFe,
        "transp"
    )

    etree.SubElement(
        transp,
        "modFrete"
    ).text = "9"

    # ==========================================
    # PAGAMENTO
    # ==========================================
    pag = etree.SubElement(
        infNFe,
        "pag"
    )

    detPag = etree.SubElement(
        pag,
        "detPag"
    )

    forma_pagamento = (
        venda.get("pagamento")
        or venda.get("forma_pagamento")
        or venda.get("tipo_pagamento")
        or "outros"
    )

    t_pag = mapear_tpag(
        forma_pagamento
    )

    etree.SubElement(
        detPag,
        "tPag"
    ).text = t_pag

    etree.SubElement(
        detPag,
        "vPag"
    ).text = f"{total_produtos:.2f}"

    # ==========================================
    # INFORMAÇÕES SUPLEMENTARES
    # ==========================================
    if qr_code_url:

        infNFeSupl = etree.SubElement(
            nfe,
            "infNFeSupl"
        )

        etree.SubElement(
            infNFeSupl,
            "qrCode"
        ).text = qr_code_url

        etree.SubElement(
            infNFeSupl,
            "urlChave"
        ).text = (
            "https://www.sistema.fazenda.sp.gov.br/"
            "NFCeConsultaPublica/Paginas/"
            "ConsultaPublica.aspx"
        )

    # ==========================================
    # RETORNO XML
    # ==========================================
    return etree.tostring(
        nfe,
        encoding="utf-8",
        xml_declaration=True
    )


# ==========================================
# DV MOD11
# ==========================================
def calcular_dv_mod11(chave):

    pesos = [2, 3, 4, 5, 6, 7, 8, 9]

    soma = 0
    peso_index = 0

    for digito in reversed(chave):

        soma += (
            int(digito) *
            pesos[peso_index]
        )

        peso_index = (
            peso_index + 1
        ) % len(pesos)

    resto = soma % 11

    dv = 11 - resto

    if dv >= 10:

        dv = 0

    return str(dv)


# ==========================================
# CHAVE ACESSO
# ==========================================
def gerar_chave_acesso(
    cUF,
    ano_mes,
    cnpj,
    modelo,
    serie,
    numero,
    tpEmis="1"
):

    cnpj = somente_numeros(
        cnpj
    )

    cNF = str(
        random.randint(
            10000000,
            99999999
        )
    )

    base = (
        f"{cUF}"
        f"{ano_mes}"
        f"{cnpj}"
        f"{modelo}"
        f"{str(serie).zfill(3)}"
        f"{str(numero).zfill(9)}"
        f"{tpEmis}"
        f"{cNF}"
    )

    dv = calcular_dv_mod11(
        base
    )

    chave = base + dv

    return chave, cNF, dv