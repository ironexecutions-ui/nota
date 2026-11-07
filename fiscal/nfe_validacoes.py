from datetime import datetime


def log(msg):
    print(f"[NFe-VALIDACAO][{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def validar_comercio_nfe(fiscal):
    """
    Validação exclusiva da NF-e modelo 55.
    Não exige CSC, série NFC-e nem numeração NFC-e.
    """
    obrigatorios = (
        "razao_social",
        "crt",
        "ambiente_emissao",
        "serie_nfe",
        "numero_inicial_nfe",
        "certificado_path",
        "inscricao_estadual",
        "codigo_municipio",
    )

    faltando = [
        campo for campo in obrigatorios
        if fiscal.get(campo) is None or str(fiscal.get(campo)).strip() == ""
    ]
    if faltando:
        raise Exception(
            "Dados fiscais para NF-e incompletos: " + ", ".join(faltando)
        )

    ambiente = str(fiscal["ambiente_emissao"]).strip().lower()
    if ambiente not in ("homologacao", "producao"):
        raise Exception("Ambiente de emissão da NF-e inválido.")

    serie = str(fiscal["serie_nfe"]).strip()
    if not serie.isdigit() or int(serie) < 1 or int(serie) > 999:
        raise Exception("Série da NF-e deve ser numérica, entre 1 e 999.")

    numero_inicial = str(fiscal["numero_inicial_nfe"]).strip()
    if not numero_inicial.isdigit() or int(numero_inicial) < 1:
        raise Exception("Número inicial da NF-e inválido.")

    crt = str(fiscal["crt"]).strip()
    if crt not in ("1", "2", "3", "4"):
        raise Exception("CRT inválido. Valores aceitos: 1, 2, 3 ou 4.")

    ie = "".join(ch for ch in str(fiscal["inscricao_estadual"]) if ch.isdigit())
    if not ie:
        raise Exception("Inscrição Estadual do emitente inválida.")

    codigo_municipio = "".join(
        ch for ch in str(fiscal["codigo_municipio"]) if ch.isdigit()
    )
    if len(codigo_municipio) != 7:
        raise Exception("Código IBGE do município do emitente deve ter 7 dígitos.")

    cnpj = "".join(ch for ch in str(fiscal.get("cnpj") or "") if ch.isdigit())
    if len(cnpj) != 14:
        raise Exception("CNPJ do emitente inválido.")

    log("Dados fiscais do emitente validados para NF-e.")
