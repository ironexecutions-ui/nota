from datetime import datetime
from zoneinfo import ZoneInfo
from lxml import etree

from .nfce_xml import (
    NFE_NS,
    log,
    somente_numeros,
    limpar_texto_xml,
    criar_elemento,
    mapear_tpag,
    gerar_icms,
    gerar_ibscbs,
    calcular_tributos_aproximados,
)


def gerar_xml_nfe(dados):

    print("\n")
    print("=" * 100)
    print("=============== INÍCIO GERAÇÃO XML NF-e ===============")
    print("=" * 100)

    comercio = dados["comercio"]
    fiscal = dados["fiscal"]
    itens = dados["itens"]
    venda = dados["venda"]

    numero_nfe = dados[
        "numero_nfe"
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
        f"Número NF-e: {numero_nfe}"
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
            f"CNPJ inválido para NF-e: {cnpj}"
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
        limpar_texto_xml(dados.get("natureza_operacao") or "VENDA DE MERCADORIA")
    )

    criar_elemento(
        ide,
        "mod",
        "55"
    )

    criar_elemento(
        ide,
        "serie",
        str(
            fiscal["serie_nfe"]
        )
    )

    criar_elemento(
        ide,
        "nNF",
        str(
            numero_nfe
        )
    )

    dh_emi = dados.get("data_emissao") or datetime.now(
        ZoneInfo("America/Sao_Paulo")
    )
    if isinstance(dh_emi, datetime):
        dh_emi = dh_emi.replace(microsecond=0).isoformat()

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
        str(dados.get("id_dest", "2")).strip()
    )

    criar_elemento(
        ide,
        "cMunFG",
        codigo_municipio
    )

    criar_elemento(
        ide,
        "tpImp",
        "1"
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

    ambiente_emissao = str(
        fiscal["ambiente_emissao"]
    ).strip().lower()

    if ambiente_emissao == "homologacao":
        tp_amb = "2"

    elif ambiente_emissao == "producao":
        tp_amb = "1"

    else:
        raise Exception(
            f"Ambiente de emissão inválido: {ambiente_emissao}"
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

    ind_pres = str(dados.get("ind_pres", "9")).strip()

    criar_elemento(
        ide,
        "indPres",
        ind_pres
    )

    # Indicador de intermediador da operação, conforme leiaute NF-e 4.00.
    # O valor deve vir dos dados da venda:
    # 0 = operação sem intermediador.
    # 1 = operação em site/plataforma de terceiros.
    if ind_pres in ("1", "2", "3", "4", "9"):
        ind_intermed = str(dados.get("ind_intermed", "0")).strip()

        if ind_intermed not in ("0", "1"):
            raise Exception(
                "Indicador do intermediador inválido. Informe 0 ou 1."
            )

        criar_elemento(
            ide,
            "indIntermed",
            ind_intermed
        )

        log(f"Indicador do intermediador NF-e: {ind_intermed}")

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
    # DESTINATÁRIO NF-e MODELO 55
    # ==========================================
    destinatario = dados.get("destinatario") or {}

    documento_dest = somente_numeros(destinatario.get("documento"))
    nome_dest = limpar_texto_xml(destinatario.get("nome"))

    if len(documento_dest) == 11:
        tag_documento = "CPF"
    elif len(documento_dest) == 14:
        tag_documento = "CNPJ"
    else:
        raise Exception("Destinatário precisa ter CPF com 11 ou CNPJ com 14 dígitos.")

    if not nome_dest:
        raise Exception("Nome do destinatário não informado.")

    dest = criar_elemento(infNFe, "dest")
    criar_elemento(dest, tag_documento, documento_dest)
    criar_elemento(dest, "xNome", nome_dest)

    ender_dest = criar_elemento(dest, "enderDest")
    campos_endereco = {
        "xLgr": limpar_texto_xml(destinatario.get("logradouro")),
        "nro": str(destinatario.get("numero") or "").strip(),
        "xBairro": limpar_texto_xml(destinatario.get("bairro")),
        "cMun": somente_numeros(destinatario.get("codigo_municipio")),
        "xMun": limpar_texto_xml(destinatario.get("municipio")),
        "UF": str(destinatario.get("uf") or "").strip().upper(),
        "CEP": somente_numeros(destinatario.get("cep")),
    }

    obrigatorios_dest = ("xLgr", "nro", "xBairro", "cMun", "xMun", "UF", "CEP")
    faltando_dest = [campo for campo in obrigatorios_dest if not campos_endereco.get(campo)]
    if faltando_dest:
        raise Exception("Endereço do destinatário incompleto: " + ", ".join(faltando_dest))
    if len(campos_endereco["cMun"]) != 7:
        raise Exception("Código IBGE do destinatário deve ter 7 dígitos.")
    if len(campos_endereco["CEP"]) != 8:
        raise Exception("CEP do destinatário deve ter 8 dígitos.")
    if len(campos_endereco["UF"]) != 2:
        raise Exception("UF do destinatário inválida.")

    criar_elemento(ender_dest, "xLgr", campos_endereco["xLgr"])
    criar_elemento(ender_dest, "nro", campos_endereco["nro"])

    complemento_dest = limpar_texto_xml(destinatario.get("complemento"))
    if complemento_dest:
        criar_elemento(ender_dest, "xCpl", complemento_dest)

    for campo in ("xBairro", "cMun", "xMun", "UF", "CEP"):
        criar_elemento(ender_dest, campo, campos_endereco[campo])

    criar_elemento(ender_dest, "cPais", "1058")
    criar_elemento(ender_dest, "xPais", "BRASIL")

    telefone_dest = somente_numeros(destinatario.get("telefone"))
    if telefone_dest:
        criar_elemento(ender_dest, "fone", telefone_dest)

    indicador_ie = str(destinatario.get("indicador_inscricao_estadual") or "9").strip()
    if indicador_ie not in ("1", "2", "9"):
        raise Exception("Indicador de IE do destinatário inválido.")
    criar_elemento(dest, "indIEDest", indicador_ie)

    ie_dest = somente_numeros(destinatario.get("inscricao_estadual"))
    if indicador_ie == "1":
        if not ie_dest:
            raise Exception("Destinatário contribuinte do ICMS precisa informar IE.")
        criar_elemento(dest, "IE", ie_dest)

    email_dest = str(destinatario.get("email") or "").strip()
    if email_dest:
        criar_elemento(dest, "email", email_dest)

    # ==========================================
    # PRODUTOS
    # ==========================================
    # ==========================================
    # PRODUTOS
    # ==========================================
    log(
        f"Gerando {len(itens)} item(ns)"
    )

    total_produtos = 0.0
    
    total_bc_ibscbs = 0.0
    total_ibs_uf = 0.0
    total_ibs_mun = 0.0
    total_ibs = 0.0
    total_cbs = 0.0
    
    # Lei 12.741/2012
    total_tributos_aproximados = 0.0
    total_tributos_federal = 0.0
    total_tributos_estadual = 0.0
    total_tributos_municipal = 0.0

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

# ==========================================
# NOME DO PRODUTO
# ==========================================

        if tp_amb == "2" and idx == 1:
            nome_produto = (
                "NOTA FISCAL EMITIDA EM AMBIENTE DE "
                "HOMOLOGACAO - SEM VALOR FISCAL"
            )
        
            log(
                "Ambiente de homologação, "
                "xProd do primeiro item alterado conforme exigência da SEFAZ"
            )
        else:
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
            item.get("quantidade") or 0
        )
        
        valor_unitario_fiscal = item.get("valor_unitario_fiscal")
        
        if valor_unitario_fiscal is not None:
            preco = float(valor_unitario_fiscal)
        else:
            preco = float(item.get("preco") or 0)
        
        valor_total_fiscal = item.get("valor_total_fiscal")
        
        if valor_total_fiscal is not None:
            valor_total_item = float(valor_total_fiscal)
        else:
            valor_total_item = quantidade * preco

        unidade_fiscal = (
            str(
                item.get(
                    "unidade_fiscal",
                    "UN"
                )
            )
            .strip()
            .upper()
        )

        eh_produto_peso = bool(
            item.get(
                "eh_produto_peso"
            )
        )

        log(
            f"ITEM XML | "
            f"ID={item.get('id')} | "
            f"Peso={eh_produto_peso} | "
            f"uCom={unidade_fiscal} | "
            f"qCom={quantidade:.4f} | "
            f"vUnCom={preco:.10f} | "
            f"vProd={valor_total_item:.2f}"
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
            unidade_fiscal
        )

        criar_elemento(
            prod,
            "qCom",
            f"{quantidade:.4f}"
        )

        criar_elemento(
            prod,
            "vUnCom",
            f"{preco:.10f}".rstrip("0").rstrip(".")
        )

        # ==========================================
        # VALOR TOTAL DO PRODUTO
        #
        # Produto normal:
        # quantidade * preço
        #
        # Produto por peso:
        # usa exatamente o valor cobrado na venda
        # ==========================================

        v_prod = round(
            valor_total_item,
            2
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
            unidade_fiscal
        )

        criar_elemento(
            prod,
            "qTrib",
            f"{quantidade:.4f}"
        )

        criar_elemento(
            prod,
            "vUnTrib",
            f"{preco:.10f}".rstrip("0").rstrip(".")
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
        
        # ==========================================
        # TRIBUTOS APROXIMADOS
        # LEI 12.741/2012
        # ==========================================
        
        tributos_aproximados = (
            calcular_tributos_aproximados(
                item,
                v_prod
            )
        )
        
        v_tot_trib_item = (
            tributos_aproximados["total"]
        )
        
        criar_elemento(
            imposto,
            "vTotTrib",
            f"{v_tot_trib_item:.2f}"
        )
        
        total_tributos_aproximados += (
            v_tot_trib_item
        )
        
        total_tributos_federal += (
            tributos_aproximados["federal"]
        )
        
        total_tributos_estadual += (
            tributos_aproximados["estadual"]
        )
        
        total_tributos_municipal += (
            tributos_aproximados["municipal"]
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
        # ==========================================
        # IBS / CBS
        # ==========================================
        valores_ibscbs = gerar_ibscbs(
            imposto,
            item,
            v_prod
        )

        total_bc_ibscbs += valores_ibscbs["vBC"]
        total_ibs_uf += valores_ibscbs["vIBSUF"]
        total_ibs_mun += valores_ibscbs["vIBSMun"]
        total_ibs += valores_ibscbs["vIBS"]
        total_cbs += valores_ibscbs["vCBS"]
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
            f"{total_tributos_aproximados:.2f}"
        )
    ]

    for tag, valor in campos_total:

        criar_elemento(
            icmsTot,
            tag,
            valor
        )
    # ==========================================
    # TOTAL IBS / CBS
    # ==========================================
    ibscbs_tot = criar_elemento(
        total,
        "IBSCBSTot"
    )

    criar_elemento(
        ibscbs_tot,
        "vBCIBSCBS",
        f"{total_bc_ibscbs:.2f}"
    )

    # ==========================================
    # TOTAL IBS
    # ==========================================
    gibs = criar_elemento(
        ibscbs_tot,
        "gIBS"
    )

    gibs_uf = criar_elemento(
        gibs,
        "gIBSUF"
    )

    criar_elemento(
        gibs_uf,
        "vDif",
        "0.00"
    )

    criar_elemento(
        gibs_uf,
        "vDevTrib",
        "0.00"
    )

    criar_elemento(
        gibs_uf,
        "vIBSUF",
        f"{total_ibs_uf:.2f}"
    )

    gibs_mun = criar_elemento(
        gibs,
        "gIBSMun"
    )

    criar_elemento(
        gibs_mun,
        "vDif",
        "0.00"
    )

    criar_elemento(
        gibs_mun,
        "vDevTrib",
        "0.00"
    )

    criar_elemento(
        gibs_mun,
        "vIBSMun",
        f"{total_ibs_mun:.2f}"
    )

    criar_elemento(
        gibs,
        "vIBS",
        f"{total_ibs:.2f}"
    )

    criar_elemento(
        gibs,
        "vCredPres",
        "0.00"
    )

    criar_elemento(
        gibs,
        "vCredPresCondSus",
        "0.00"
    )

    # ==========================================
    # TOTAL CBS
    # ==========================================
    gcbs = criar_elemento(
        ibscbs_tot,
        "gCBS"
    )

    criar_elemento(
        gcbs,
        "vDif",
        "0.00"
    )

    criar_elemento(
        gcbs,
        "vDevTrib",
        "0.00"
    )

    criar_elemento(
        gcbs,
        "vCBS",
        f"{total_cbs:.2f}"
    )

    criar_elemento(
        gcbs,
        "vCredPres",
        "0.00"
    )

    criar_elemento(
        gcbs,
        "vCredPresCondSus",
        "0.00"
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
    
    # Cartão de crédito ou débito
    if t_pag in ["03", "04"]:
    
        card = criar_elemento(
            detPag,
            "card"
        )
    
        criar_elemento(
            card,
            "tpIntegra",
            "2"
        )
    
        log(
            f"Dados de cartão adicionados | "
            f"tPag={t_pag} | tpIntegra=2"
        )

    # NF-e modelo 55 não utiliza infNFeSupl/QR Code de NF-e.

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
            "ERRO DE SINTAXE NO XML NF-e"
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
        "=============== XML NF-e GERADO "
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
        "=============== FIM XML NF-e "
        "GERADO ==============="
    )
    print("=" * 100)
    print("\n")

    log(
        "===== XML NF-e GERADO COM SUCESSO ====="
    )

    return xml_bytes
