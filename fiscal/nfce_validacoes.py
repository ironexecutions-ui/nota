from datetime import datetime


def log(msg):
    print(
        f"[NFCe-VALIDACAO]"
        f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    )


def validar_comercio_fiscal(fiscal):

    log("Iniciando validação fiscal do comércio")

    obrigatorios = [
        "razao_social",
        "crt",
        "ambiente_emissao",
        "serie_nfce",
        "numero_inicial_nfce",
        "certificado_path",
        "csc_id",
        "csc_token"
    ]

    faltando = []

    for campo in obrigatorios:

        valor = fiscal.get(campo)

        if valor is None or str(valor).strip() == "":
            faltando.append(campo)

    if faltando:

        msg = (
            "Dados fiscais do comércio incompletos: "
            + ", ".join(faltando)
        )

        log(f"ERRO: {msg}")

        raise Exception(msg)

    # ===============================
    # AMBIENTE
    # ===============================

    log("Validando ambiente de emissão")

    ambiente = str(
        fiscal["ambiente_emissao"]
    ).strip().lower()

    if ambiente not in ["homologacao", "producao"]:
        raise Exception(
            "Ambiente de emissão inválido"
        )

    # ===============================
    # SÉRIE NFC-e
    # ===============================

    log("Validando série da NFC-e")

    serie = str(
        fiscal["serie_nfce"]
    ).strip()

    if not serie.isdigit():
        raise Exception(
            "Série da NFC-e inválida"
        )

    if int(serie) <= 0:
        raise Exception(
            "Série da NFC-e deve ser maior que zero"
        )

    # ===============================
    # NÚMERO INICIAL
    # ===============================

    log("Validando número inicial da NFC-e")

    numero_inicial = str(
        fiscal["numero_inicial_nfce"]
    ).strip()

    if not numero_inicial.isdigit():
        raise Exception(
            "Número inicial da NFC-e inválido"
        )

    if int(numero_inicial) <= 0:
        raise Exception(
            "Número inicial da NFC-e deve ser maior que zero"
        )

    # ===============================
    # CRT
    # ===============================

    log("Validando CRT")

    crt = str(
        fiscal["crt"]
    ).strip()

    log(f"CRT RECEBIDO: [{crt}]")

    if crt not in ["1", "2", "3", "4"]:
        raise Exception(
            "CRT inválido. "
            "Use 1 (Simples Nacional), "
            "2, 3 ou 4 (MEI)"
        )

    # ===============================
    # CSC
    # ===============================

    log("Validando CSC")

    csc_id = str(
        fiscal["csc_id"]
    ).strip()

    if not csc_id.isdigit():
        raise Exception(
            "CSC ID inválido"
        )

    csc_token = str(
        fiscal["csc_token"]
    ).strip()

    if len(csc_token) < 10:
        raise Exception(
            "CSC Token inválido"
        )

    log(
        "Validação fiscal do comércio "
        "concluída com sucesso"
    )


def validar_produto_fiscal(produto):

    log(
        f"Validando produto fiscal | "
        f"Produto ID: {produto.get('id')}"
    )

    # ===============================
    # CAMPOS OBRIGATÓRIOS
    # ===============================

    obrigatorios = [
        "cfop",
        "origem",
        "cst_csosn"
    ]

    faltando = []

    for campo in obrigatorios:

        valor = produto.get(campo)

        if valor is None or str(valor).strip() == "":
            faltando.append(campo)

    if faltando:

        msg = (
            "Produto sem dados fiscais obrigatórios: "
            + ", ".join(faltando)
        )

        log(f"ERRO: {msg}")

        raise Exception(msg)

    # ===============================
    # CFOP
    # ===============================

    log("Validando CFOP")

    cfop = str(
        produto["cfop"]
    ).strip()

    if not cfop.isdigit():
        raise Exception(
            "CFOP inválido"
        )

    # ===============================
    # ORIGEM
    # ===============================

    log("Validando origem do produto")

    origem = str(
        produto["origem"]
    ).strip()

    origens_validas = [
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8"
    ]

    if origem not in origens_validas:
        raise Exception(
            "Origem do produto inválida"
        )

    # ===============================
    # CST / CSOSN
    # ===============================

    log("Validando CST/CSOSN")

    cst_csosn = str(
        produto["cst_csosn"]
    ).strip()

    log(
        f"CST/CSOSN RECEBIDO: "
        f"[{cst_csosn}]"
    )

    if not cst_csosn.isdigit():
        raise Exception(
            "CST/CSOSN inválido"
        )

    # ===============================
    # CRT
    # ===============================

    crt = str(
        produto.get("crt", "")
    ).strip()

    log(
        f"CRT RECEBIDO NO PRODUTO: "
        f"[{crt}]"
    )

    if crt not in ["1", "2", "3", "4"]:
        raise Exception(
            f"CRT inválido no produto: {crt}"
        )

    # ===============================
    # CST x CSOSN
    # ===============================

    log(
        f"Validando CST/CSOSN "
        f"conforme CRT ({crt})"
    )

    if crt in ["1", "4"]:

        # Simples Nacional / MEI usa CSOSN

        if len(cst_csosn) != 3:
            raise Exception(
                "CSOSN inválido para "
                "Simples Nacional/MEI"
            )

        log(
            f"CSOSN {cst_csosn} aceito "
            f"para CRT {crt}"
        )

    else:

        # Regime normal usa CST

        if len(cst_csosn) != 2:
            raise Exception(
                "CST inválido para regime normal"
            )

        log(
            f"CST {cst_csosn} aceito "
            f"para CRT {crt}"
        )

    # ===============================
    # PRODUTO x SERVIÇO
    # ===============================

    tipo = str(
        produto.get("tipo", "produto")
    ).strip().lower()

    log(f"Tipo do item: {tipo}")

    if tipo == "servico":

        if not produto.get("codigo_servico"):
            raise Exception(
                "Serviço sem código de serviço"
            )

    else:

        # ===============================
        # NCM
        # ===============================

        log("Validando NCM")

        ncm = str(
            produto.get("ncm", "")
        ).replace(".", "").strip()

        if not ncm:
            raise Exception(
                "Produto sem NCM"
            )

        if not ncm.isdigit():
            raise Exception(
                "NCM inválido"
            )

        log(
            f"NCM validado: {ncm}"
        )

    log(
        f"Produto {produto.get('id')} "
        f"validado com sucesso"
    )
