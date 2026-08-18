from lxml import etree
from datetime import datetime
from zoneinfo import ZoneInfo
import unicodedata
import re
import random


# ==========================================
# CONSTANTES XML
# ==========================================
NFE_NS = "http://www.portalfiscal.inf.br/nfe"


# ==========================================
# LOG
# ==========================================
def log(msg):
    print(
        f"[NFCe-XML]"
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{msg}"
    )


# ==========================================
# LIMPEZA
# ==========================================
def somente_numeros(valor):

    if valor is None:
        return ""

    return re.sub(
        r"\D",
        "",
        str(valor)
    )


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
# CRIA ELEMENTO NO NAMESPACE NFE
# ==========================================
def criar_elemento(
    pai,
    nome,
    texto=None,
    **atributos
):

    elemento = etree.SubElement(
        pai,
        etree.QName(
            NFE_NS,
            nome
        ),
        **atributos
    )

    if texto is not None:
        elemento.text = str(texto)

    return elemento


# ==========================================
# PAGAMENTO
# ==========================================
def mapear_tpag(pagamento):

    if pagamento is None:
        return "99"

    pagamento = (
        str(pagamento)
        .strip()
        .lower()
    )

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

    return mapa.get(
        pagamento,
        "99"
    )


# ==========================================
# ICMS
# ==========================================
def gerar_icms(
    imposto,
    item,
    origem,
    cst_csosn
):

    log(
        f"Gerando ICMS do produto "
        f"{item.get('id')}"
    )

    icms = criar_elemento(
        imposto,
        "ICMS"
    )

    crt = str(
        item.get(
            "crt",
            ""
        )
    ).strip()

    codigo = somente_numeros(
        cst_csosn
    )

    log(
        f"CRT: {crt} | "
        f"CST/CSOSN: {codigo}"
    )

    # ==========================================
    # SIMPLES NACIONAL
    # ==========================================
    if crt == "1":

        # ==========================================
        # CSOSN 102 / 103 / 300 / 400
        # ==========================================
        if codigo in [
            "102",
            "103",
            "300",
            "400"
        ]:

            grupo = criar_elemento(
                icms,
                "ICMSSN102"
            )

            criar_elemento(
                grupo,
                "orig",
                origem
            )

            criar_elemento(
                grupo,
                "CSOSN",
                codigo
            )

            log(
                f"ICMSSN102 gerado "
                f"com CSOSN {codigo}"
            )

            return

        # ==========================================
        # CSOSN 500
        # ==========================================
        if codigo == "500":

            grupo = criar_elemento(
                icms,
                "ICMSSN500"
            )

            criar_elemento(
                grupo,
                "orig",
                origem
            )

            criar_elemento(
                grupo,
                "CSOSN",
                codigo
            )

            log("ICMSSN500 gerado")

            return

        raise Exception(
            f"CSOSN {codigo} ainda não implementado "
            f"para o produto {item.get('id')}"
        )

    # ==========================================
    # REGIME NORMAL
    # ==========================================
    if crt in [
        "2",
        "3"
    ]:

        # ==========================================
        # CST 00
        # ==========================================
        if codigo == "00":

            grupo = criar_elemento(
                icms,
                "ICMS00"
            )

            criar_elemento(
                grupo,
                "orig",
                origem
            )

            criar_elemento(
                grupo,
                "CST",
                codigo
            )

            criar_elemento(
                grupo,
                "modBC",
                "3"
            )

            criar_elemento(
                grupo,
                "vBC",
                "0.00"
            )

            criar_elemento(
                grupo,
                "pICMS",
                "0.00"
            )

            criar_elemento(
                grupo,
                "vICMS",
                "0.00"
            )

            return

        # ==========================================
        # CST 40 / 41 / 50
        # ==========================================
        if codigo in [
            "40",
            "41",
            "50"
        ]:

            grupo = criar_elemento(
                icms,
                "ICMS40"
            )

            criar_elemento(
                grupo,
                "orig",
                origem
            )

            criar_elemento(
                grupo,
                "CST",
                codigo
            )

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
def gerar_xml_nfce(
    dados,
    qr_code_url=None
):

    print("\n")
    print("=" * 100)
    print("=============== INÍCIO GERAÇÃO XML NFC-e ===============")
    print("=" * 100)

    comercio = dados["comercio"]
    fiscal = dados["fiscal"]
    itens = dados["itens"]
    venda = dados["venda"]

    numero_nfce = dados[
        "numero_nfce"
    ]

    chave_acesso = dados[
        "chave_acesso"
    ]

    cNF = dados[
        "cNF"
    ]

    cDV = dados[
        "cDV"
    ]

    log(
        f"Número NFC-e: {numero_nfce}"
    )

    log(
        f"Chave: {chave_acesso}"
    )

    log(
        f"cNF: {cNF}"
    )

    log(
        f"cDV: {cDV}"
    )

    # ==========================================
    # VALIDA CHAVE
    # ==========================================
    if len(str(chave_acesso)) != 44:

        raise Exception(
            "Chave de acesso deve possuir "
            "44 dígitos"
        )

    if not str(
        chave_acesso
    ).isdigit():

        raise Exception(
            "Chave de acesso contém "
            "caracteres inválidos"
        )

    # ==========================================
    # LIMPEZA FISCAL
    # ==========================================
    log("Preparando dados fiscais")

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
        comercio.get(
            "telefone",
            ""
        )
    )

    codigo_municipio = somente_numeros(
        comercio[
            "codigo_municipio"
        ]
    )

    # ==========================================
    # VALIDAÇÕES BÁSICAS
    # ==========================================
    if len(cnpj) != 14:

        raise Exception(
            f"CNPJ inválido para NFC-e: {cnpj}"
        )

    if not ie:

        raise Exception(
            "Inscrição Estadual não informada"
        )

    if len(codigo_municipio) != 7:

        raise Exception(
            f"Código IBGE do município inválido: "
            f"{codigo_municipio}"
        )

    # ==========================================
    # XML BASE
    # ==========================================
    log("Criando elemento raiz NFe")

    nfe = etree.Element(
        etree.QName(
            NFE_NS,
            "NFe"
        ),
        nsmap={
            None: NFE_NS
        }
    )

    infNFe = criar_elemento(
        nfe,
        "infNFe",
        Id=f"NFe{chave_acesso}",
        versao="4.00"
    )

    # ==========================================
    # IDE
    # ==========================================
    log("Gerando bloco ide")

    ide = criar_elemento(
        infNFe,
        "ide"
    )

    criar_elemento(
        ide,
        "cUF",
        chave_acesso[:2]
    )

    criar_elemento(
        ide,
        "cNF",
        cNF
    )

    criar_elemento(
        ide,
        "natOp",
        "VENDA DE MERCADORIA"
    )

    criar_elemento(
        ide,
        "mod",
        "65"
    )

    criar_elemento(
        ide,
        "serie",
        str(
            fiscal["serie_nfce"]
        )
    )

    criar_elemento(
        ide,
        "nNF",
        str(
            numero_nfce
        )
    )

    dh_emi = datetime.now(
        ZoneInfo(
            "America/Sao_Paulo"
        )
    ).replace(
        microsecond=0
    ).isoformat()

    criar_elemento(
        ide,
        "dhEmi",
        dh_emi
    )

    criar_elemento(
        ide,
        "tpNF",
        "1"
    )

    criar_elemento(
        ide,
        "idDest",
        "1"
    )

    criar_elemento(
        ide,
        "cMunFG",
        codigo_municipio
    )

    criar_elemento(
        ide,
        "tpImp",
        "4"
    )

    criar_elemento(
        ide,
        "tpEmis",
        "1"
    )

    criar_elemento(
        ide,
        "cDV",
        cDV
    )

    tp_amb = (
        "2"
        if str(
            fiscal["ambiente_emissao"]
        ).strip().lower()
        == "homologacao"
        else "1"
    )

    criar_elemento(
        ide,
        "tpAmb",
        tp_amb
    )

    criar_elemento(
        ide,
        "finNFe",
        "1"
    )

    criar_elemento(
        ide,
        "indFinal",
        "1"
    )

    criar_elemento(
        ide,
        "indPres",
        "1"
    )

    criar_elemento(
        ide,
        "procEmi",
        "0"
    )

    criar_elemento(
        ide,
        "verProc",
        "IRON1.0"
    )

    log("Bloco ide concluído")

    # ==========================================
    # EMITENTE
    # ==========================================
    log("Gerando emitente")

    emit = criar_elemento(
        infNFe,
        "emit"
    )

    criar_elemento(
        emit,
        "CNPJ",
        cnpj
    )

    criar_elemento(
        emit,
        "xNome",
        razao_social
    )

    nome_fantasia = limpar_texto_xml(
        comercio.get(
            "nome",
            comercio.get(
                "nome_fantasia",
                razao_social
            )
        )
    )

    if nome_fantasia:

        criar_elemento(
            emit,
            "xFant",
            nome_fantasia
        )

    # ==========================================
    # ENDEREÇO EMITENTE
    # ==========================================
    ender = criar_elemento(
        emit,
        "enderEmit"
    )

    criar_elemento(
        ender,
        "xLgr",
        rua
    )

    criar_elemento(
        ender,
        "nro",
        numero_endereco
    )

    criar_elemento(
        ender,
        "xBairro",
        bairro
    )

    criar_elemento(
        ender,
        "cMun",
        codigo_municipio
    )

    criar_elemento(
        ender,
        "xMun",
        cidade
    )

    criar_elemento(
        ender,
        "UF",
        estado
    )

    if cep:

        criar_elemento(
            ender,
            "CEP",
            cep
        )

    criar_elemento(
        ender,
        "cPais",
        "1058"
    )

    criar_elemento(
        ender,
        "xPais",
        "BRASIL"
    )

    if telefone:

        criar_elemento(
            ender,
            "fone",
            telefone
        )

    criar_elemento(
        emit,
        "IE",
        ie
    )

    criar_elemento(
        emit,
        "CRT",
        str(
            fiscal["crt"]
        ).strip()
    )

    log("Emitente concluído")

    # ==========================================
    # DESTINATÁRIO
    # ==========================================
    cpf = somente_numeros(
        venda.get(
            "cpf_consumidor"
        )
    )

    if cpf:

        log(
            f"Gerando destinatário CPF: {cpf}"
        )

        if len(cpf) != 11:

            raise Exception(
                "CPF do consumidor inválido"
            )

        dest = criar_elemento(
            infNFe,
            "dest"
        )

        criar_elemento(
            dest,
            "CPF",
            cpf
        )

        criar_elemento(
            dest,
            "indIEDest",
            "9"
        )

    else:

        log(
            "NFC-e sem identificação "
            "do consumidor"
        )

    # ==========================================
    # PRODUTOS
    # ==========================================
    log(
        f"Gerando {len(itens)} item(ns)"
    )

    total_produtos = 0.0

    for idx, item in enumerate(
        itens,
        start=1
    ):

        log(
            f"Gerando item {idx} | "
            f"ID {item.get('id')}"
        )

        det = criar_elemento(
            infNFe,
            "det",
            nItem=str(idx)
        )

        prod = criar_elemento(
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

        if len(ncm) != 8:

            raise Exception(
                f"NCM inválido no produto "
                f"{item.get('id')}: {ncm}"
            )

        if len(cfop) != 4:

            raise Exception(
                f"CFOP inválido no produto "
                f"{item.get('id')}: {cfop}"
            )

        if quantidade <= 0:

            raise Exception(
                f"Quantidade inválida no produto "
                f"{item.get('id')}"
            )

        if preco < 0:

            raise Exception(
                f"Preço inválido no produto "
                f"{item.get('id')}"
            )

        criar_elemento(
            prod,
            "cProd",
            str(
                item["id"]
            )
        )

        criar_elemento(
            prod,
            "cEAN",
            "SEM GTIN"
        )

        criar_elemento(
            prod,
            "xProd",
            nome_produto
        )

        criar_elemento(
            prod,
            "NCM",
            ncm
        )

        criar_elemento(
            prod,
            "CFOP",
            cfop
        )

        criar_elemento(
            prod,
            "uCom",
            "UN"
        )

        criar_elemento(
            prod,
            "qCom",
            f"{quantidade:.4f}"
        )

        criar_elemento(
            prod,
            "vUnCom",
            f"{preco:.4f}"
        )

        v_prod = (
            quantidade *
            preco
        )

        criar_elemento(
            prod,
            "vProd",
            f"{v_prod:.2f}"
        )

        criar_elemento(
            prod,
            "cEANTrib",
            "SEM GTIN"
        )

        criar_elemento(
            prod,
            "uTrib",
            "UN"
        )

        criar_elemento(
            prod,
            "qTrib",
            f"{quantidade:.4f}"
        )

        criar_elemento(
            prod,
            "vUnTrib",
            f"{preco:.4f}"
        )

        criar_elemento(
            prod,
            "indTot",
            "1"
        )

        total_produtos += v_prod

        # ==========================================
        # IMPOSTOS
        # ==========================================
        imposto = criar_elemento(
            det,
            "imposto"
        )

        criar_elemento(
            imposto,
            "vTotTrib",
            "0.00"
        )

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
        pis = criar_elemento(
            imposto,
            "PIS"
        )

        pis_nt = criar_elemento(
            pis,
            "PISNT"
        )

        criar_elemento(
            pis_nt,
            "CST",
            "08"
        )

        # ==========================================
        # COFINS
        # ==========================================
        cofins = criar_elemento(
            imposto,
            "COFINS"
        )

        cofins_nt = criar_elemento(
            cofins,
            "COFINSNT"
        )

        criar_elemento(
            cofins_nt,
            "CST",
            "08"
        )

        log(
            f"Item {idx} concluído | "
            f"Valor: {v_prod:.2f}"
        )

    log(
        f"Total dos produtos: "
        f"{total_produtos:.2f}"
    )

    # ==========================================
    # TOTAL
    # ==========================================
    log("Gerando total")

    total = criar_elemento(
        infNFe,
        "total"
    )

    icmsTot = criar_elemento(
        total,
        "ICMSTot"
    )

    # IMPORTANTE:
    # ordem das tags conforme estrutura do ICMSTot
    campos_total = [
        (
            "vBC",
            "0.00"
        ),
        (
            "vICMS",
            "0.00"
        ),
        (
            "vICMSDeson",
            "0.00"
        ),
        (
            "vFCP",
            "0.00"
        ),
        (
            "vBCST",
            "0.00"
        ),
        (
            "vST",
            "0.00"
        ),
        (
            "vFCPST",
            "0.00"
        ),
        (
            "vFCPSTRet",
            "0.00"
        ),
        (
            "vProd",
            f"{total_produtos:.2f}"
        ),
        (
            "vFrete",
            "0.00"
        ),
        (
            "vSeg",
            "0.00"
        ),
        (
            "vDesc",
            "0.00"
        ),
        (
            "vII",
            "0.00"
        ),
        (
            "vIPI",
            "0.00"
        ),
        (
            "vIPIDevol",
            "0.00"
        ),
        (
            "vPIS",
            "0.00"
        ),
        (
            "vCOFINS",
            "0.00"
        ),
        (
            "vOutro",
            "0.00"
        ),
        (
            "vNF",
            f"{total_produtos:.2f}"
        ),
        (
            "vTotTrib",
            "0.00"
        )
    ]

    for tag, valor in campos_total:

        criar_elemento(
            icmsTot,
            tag,
            valor
        )

    # ==========================================
    # TRANSPORTE
    # ==========================================
    log("Gerando transporte")

    transp = criar_elemento(
        infNFe,
        "transp"
    )

    criar_elemento(
        transp,
        "modFrete",
        "9"
    )

    # ==========================================
    # PAGAMENTO
    # ==========================================
    log("Gerando pagamento")

    pag = criar_elemento(
        infNFe,
        "pag"
    )

    detPag = criar_elemento(
        pag,
        "detPag"
    )

    forma_pagamento = (
        venda.get(
            "pagamento"
        )
        or venda.get(
            "forma_pagamento"
        )
        or venda.get(
            "tipo_pagamento"
        )
        or "outros"
    )

    t_pag = mapear_tpag(
        forma_pagamento
    )

    log(
        f"Forma pagamento: "
        f"{forma_pagamento}"
    )

    log(
        f"tPag: {t_pag}"
    )

    criar_elemento(
        detPag,
        "tPag",
        t_pag
    )

    criar_elemento(
        detPag,
        "vPag",
        f"{total_produtos:.2f}"
    )

    # ==========================================
    # INFORMAÇÕES SUPLEMENTARES
    # ==========================================
    if qr_code_url:

        log(
            "Adicionando infNFeSupl"
        )

        infNFeSupl = criar_elemento(
            nfe,
            "infNFeSupl"
        )

        criar_elemento(
            infNFeSupl,
            "qrCode",
            qr_code_url
        )

        criar_elemento(
            infNFeSupl,
            "urlChave",
            (
                "https://www.sistema.fazenda.sp.gov.br/"
                "NFCeConsultaPublica/Paginas/"
                "ConsultaPublica.aspx"
            )
        )

    else:

        log(
            "qr_code_url não informado. "
            "infNFeSupl não será criado nesta etapa."
        )

    # ==========================================
    # XML FINAL
    # ==========================================
    log("Serializando XML")

    xml_bytes = etree.tostring(
        nfe,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False
    )

    # ==========================================
    # TESTE DE PARSE
    # ==========================================
    log(
        "Validando sintaxe do XML gerado"
    )

    try:

        xml_teste = etree.fromstring(
            xml_bytes
        )

        log(
            f"XML válido. Raiz: "
            f"{xml_teste.tag}"
        )

    except etree.XMLSyntaxError as e:

        print("\n")
        print("!" * 100)
        print(
            "ERRO DE SINTAXE NO XML NFC-e"
        )
        print("!" * 100)
        print(str(e))
        print("!" * 100)

        raise

    # ==========================================
    # DEBUG COMPLETO
    # ==========================================
    print("\n")
    print("=" * 100)
    print(
        "=============== XML NFC-e GERADO "
        "ANTES DA ASSINATURA ==============="
    )
    print("=" * 100)

    print(
        xml_bytes.decode(
            "utf-8"
        )
    )

    print("=" * 100)
    print(
        "=============== FIM XML NFC-e "
        "GERADO ==============="
    )
    print("=" * 100)
    print("\n")

    log(
        "===== XML NFC-e GERADO COM SUCESSO ====="
    )

    return xml_bytes


# ==========================================
# DV MOD11
# ==========================================
def calcular_dv_mod11(chave):

    pesos = [
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9
    ]

    soma = 0
    peso_index = 0

    for digito in reversed(
        chave
    ):

        soma += (
            int(digito)
            *
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

    log(
        "Gerando chave de acesso"
    )

    cUF = somente_numeros(
        cUF
    )

    ano_mes = somente_numeros(
        ano_mes
    )

    cnpj = somente_numeros(
        cnpj
    )

    modelo = somente_numeros(
        modelo
    )

    serie = somente_numeros(
        serie
    )

    numero = somente_numeros(
        numero
    )

    tpEmis = somente_numeros(
        tpEmis
    )

    if len(cUF) != 2:

        raise Exception(
            f"cUF inválido: {cUF}"
        )

    if len(ano_mes) != 4:

        raise Exception(
            f"AAMM inválido: {ano_mes}"
        )

    if len(cnpj) != 14:

        raise Exception(
            f"CNPJ inválido para chave: "
            f"{cnpj}"
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
        f"{modelo.zfill(2)}"
        f"{serie.zfill(3)}"
        f"{numero.zfill(9)}"
        f"{tpEmis}"
        f"{cNF}"
    )

    if len(base) != 43:

        raise Exception(
            f"Base da chave possui "
            f"{len(base)} dígitos, "
            f"esperado: 43 | "
            f"Base: {base}"
        )

    dv = calcular_dv_mod11(
        base
    )

    chave = (
        base +
        dv
    )

    if len(chave) != 44:

        raise Exception(
            f"Chave gerada possui "
            f"{len(chave)} dígitos"
        )

    log(
        f"Chave gerada: {chave}"
    )

    log(
        f"cNF: {cNF} | "
        f"DV: {dv}"
    )

    return (
        chave,
        cNF,
        dv
    )