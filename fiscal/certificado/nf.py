import os
import random
import tempfile
import warnings
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import urllib3

from lxml import etree

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)

from signxml import (
    XMLSigner,
    XMLVerifier,
    methods,
    SignatureConfiguration,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PFX_PATH = os.path.join(
    BASE_DIR,
    "enya.pfx"
)

SENHA_PFX = "12345678"

URL_SEFAZ = (
    "https://homologacao.nfce.fazenda.sp.gov.br/"
    "ws/NFeAutorizacao4.asmx"
)

NFE_NS = "http://www.portalfiscal.inf.br/nfe"

DS_NS = "http://www.w3.org/2000/09/xmldsig#"

CNPJ = "62712093000134"

UF = "SP"

CUF = "35"

CODIGO_MUNICIPIO = "3550308"

IE = "PREENCHA_A_IE_REAL"

SERIE = 1

NUMERO_NFCE = random.randint(
    100000,
    900000
)

CSC_ID = "1"

CSC_TOKEN = ""


# ============================================================
# DESABILITAR WARNING SOMENTE PARA TESTE
# ============================================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

warnings.filterwarnings(
    "ignore"
)


# ============================================================
# LOG
# ============================================================

def titulo(texto):

    print()
    print("=" * 100)
    print(texto)
    print("=" * 100)


def log(texto):

    print(texto)


# ============================================================
# SOMENTE NÚMEROS
# ============================================================

def somente_numeros(valor):

    return re.sub(
        r"\D",
        "",
        str(valor)
    )


# ============================================================
# DV CHAVE NFC-e
# ============================================================

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

    for digito in reversed(chave):

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


# ============================================================
# GERAR CHAVE NFC-e
# ============================================================

def gerar_chave():

    agora = datetime.now(
        ZoneInfo(
            "America/Sao_Paulo"
        )
    )

    aamm = agora.strftime(
        "%y%m"
    )

    modelo = "65"

    serie = str(
        SERIE
    ).zfill(3)

    numero = str(
        NUMERO_NFCE
    ).zfill(9)

    tp_emis = "1"

    cnf = str(
        random.randint(
            10000000,
            99999999
        )
    )

    base = (
        CUF
        + aamm
        + CNPJ
        + modelo
        + serie
        + numero
        + tp_emis
        + cnf
    )

    if len(base) != 43:

        raise Exception(
            f"Base da chave inválida. "
            f"Possui {len(base)} dígitos."
        )

    dv = calcular_dv_mod11(
        base
    )

    chave = (
        base
        +
        dv
    )

    return (
        chave,
        cnf,
        dv
    )


# ============================================================
# ABRIR PFX
# ============================================================

def abrir_pfx():

    titulo(
        "[1] ABRINDO CERTIFICADO PFX"
    )

    log(
        f"PFX: {PFX_PATH}"
    )

    if not os.path.exists(
        PFX_PATH
    ):

        raise Exception(
            f"PFX não encontrado: "
            f"{PFX_PATH}"
        )

    with open(
        PFX_PATH,
        "rb"
    ) as arquivo:

        dados_pfx = arquivo.read()

    private_key, certificate, adicionais = (
        pkcs12.load_key_and_certificates(
            dados_pfx,
            SENHA_PFX.encode(
                "utf-8"
            )
        )
    )

    if private_key is None:

        raise Exception(
            "PFX não contém chave privada."
        )

    if certificate is None:

        raise Exception(
            "PFX não contém certificado."
        )

    log("")
    log("[OK] PFX aberto.")
    log("")

    log("SUBJECT:")
    log(
        certificate.subject.rfc4514_string()
    )

    log("")
    log("ISSUER:")
    log(
        certificate.issuer.rfc4514_string()
    )

    log("")
    log("SERIAL:")
    log(
        certificate.serial_number
    )

    log("")
    log("VALIDADE:")

    log(
        f"Início: "
        f"{certificate.not_valid_before_utc}"
    )

    log(
        f"Fim: "
        f"{certificate.not_valid_after_utc}"
    )

    log("")

    log(
        f"Certificados adicionais: "
        f"{len(adicionais or [])}"
    )

    return (
        private_key,
        certificate,
        adicionais or []
    )


# ============================================================
# CRIAR ELEMENTO
# ============================================================

def elemento(
    pai,
    nome,
    texto=None,
    **atributos
):

    el = etree.SubElement(
        pai,
        etree.QName(
            NFE_NS,
            nome
        ),
        **atributos
    )

    if texto is not None:

        el.text = str(
            texto
        )

    return el


# ============================================================
# GERAR XML NFC-e DE TESTE
# ============================================================

def gerar_xml():

    titulo(
        "[2] GERANDO NFC-e DE TESTE"
    )

    chave, cnf, dv = gerar_chave()

    log(
        f"Chave: {chave}"
    )

    log(
        f"cNF: {cnf}"
    )

    log(
        f"cDV: {dv}"
    )

    agora = datetime.now(
        ZoneInfo(
            "America/Sao_Paulo"
        )
    ).replace(
        microsecond=0
    )

    nfe = etree.Element(
        etree.QName(
            NFE_NS,
            "NFe"
        ),
        nsmap={
            None: NFE_NS
        }
    )

    inf_nfe = elemento(
        nfe,
        "infNFe",
        Id=f"NFe{chave}",
        versao="4.00"
    )

    # ========================================================
    # IDE
    # ========================================================

    ide = elemento(
        inf_nfe,
        "ide"
    )

    elemento(
        ide,
        "cUF",
        CUF
    )

    elemento(
        ide,
        "cNF",
        cnf
    )

    elemento(
        ide,
        "natOp",
        "VENDA"
    )

    elemento(
        ide,
        "mod",
        "65"
    )

    elemento(
        ide,
        "serie",
        str(SERIE)
    )

    elemento(
        ide,
        "nNF",
        str(NUMERO_NFCE)
    )

    elemento(
        ide,
        "dhEmi",
        agora.isoformat()
    )

    elemento(
        ide,
        "tpNF",
        "1"
    )

    elemento(
        ide,
        "idDest",
        "1"
    )

    elemento(
        ide,
        "cMunFG",
        CODIGO_MUNICIPIO
    )

    elemento(
        ide,
        "tpImp",
        "4"
    )

    elemento(
        ide,
        "tpEmis",
        "1"
    )

    elemento(
        ide,
        "cDV",
        dv
    )

    elemento(
        ide,
        "tpAmb",
        "2"
    )

    elemento(
        ide,
        "finNFe",
        "1"
    )

    elemento(
        ide,
        "indFinal",
        "1"
    )

    elemento(
        ide,
        "indPres",
        "1"
    )

    elemento(
        ide,
        "procEmi",
        "0"
    )

    elemento(
        ide,
        "verProc",
        "IRON-TESTE-SIGNXML"
    )

    # ========================================================
    # EMITENTE
    # ========================================================

    emit = elemento(
        inf_nfe,
        "emit"
    )

    elemento(
        emit,
        "CNPJ",
        CNPJ
    )

    elemento(
        emit,
        "xNome",
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO"
    )

    ender_emit = elemento(
        emit,
        "enderEmit"
    )

    elemento(
        ender_emit,
        "xLgr",
        "RUA TESTE"
    )

    elemento(
        ender_emit,
        "nro",
        "100"
    )

    elemento(
        ender_emit,
        "xBairro",
        "CENTRO"
    )

    elemento(
        ender_emit,
        "cMun",
        CODIGO_MUNICIPIO
    )

    elemento(
        ender_emit,
        "xMun",
        "SAO PAULO"
    )

    elemento(
        ender_emit,
        "UF",
        UF
    )

    elemento(
        ender_emit,
        "CEP",
        "01001000"
    )

    elemento(
        ender_emit,
        "cPais",
        "1058"
    )

    elemento(
        ender_emit,
        "xPais",
        "BRASIL"
    )

    elemento(
        emit,
        "IE",
        somente_numeros(
            IE
        )
    )

    elemento(
        emit,
        "CRT",
        "1"
    )

    # ========================================================
    # PRODUTO
    # ========================================================

    det = elemento(
        inf_nfe,
        "det",
        nItem="1"
    )

    prod = elemento(
        det,
        "prod"
    )

    elemento(
        prod,
        "cProd",
        "TESTE001"
    )

    elemento(
        prod,
        "cEAN",
        "SEM GTIN"
    )

    elemento(
        prod,
        "xProd",
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    )

    elemento(
        prod,
        "NCM",
        "61091000"
    )

    elemento(
        prod,
        "CFOP",
        "5102"
    )

    elemento(
        prod,
        "uCom",
        "UN"
    )

    elemento(
        prod,
        "qCom",
        "1.0000"
    )

    elemento(
        prod,
        "vUnCom",
        "1.0000"
    )

    elemento(
        prod,
        "vProd",
        "1.00"
    )

    elemento(
        prod,
        "cEANTrib",
        "SEM GTIN"
    )

    elemento(
        prod,
        "uTrib",
        "UN"
    )

    elemento(
        prod,
        "qTrib",
        "1.0000"
    )

    elemento(
        prod,
        "vUnTrib",
        "1.0000"
    )

    elemento(
        prod,
        "indTot",
        "1"
    )

    # ========================================================
    # IMPOSTOS
    # ========================================================

    imposto = elemento(
        det,
        "imposto"
    )

    elemento(
        imposto,
        "vTotTrib",
        "0.00"
    )

    icms = elemento(
        imposto,
        "ICMS"
    )

    icmssn102 = elemento(
        icms,
        "ICMSSN102"
    )

    elemento(
        icmssn102,
        "orig",
        "0"
    )

    elemento(
        icmssn102,
        "CSOSN",
        "102"
    )

    pis = elemento(
        imposto,
        "PIS"
    )

    pisnt = elemento(
        pis,
        "PISNT"
    )

    elemento(
        pisnt,
        "CST",
        "08"
    )

    cofins = elemento(
        imposto,
        "COFINS"
    )

    cofinsnt = elemento(
        cofins,
        "COFINSNT"
    )

    elemento(
        cofinsnt,
        "CST",
        "08"
    )

    # ========================================================
    # TOTAL
    # ========================================================

    total = elemento(
        inf_nfe,
        "total"
    )

    icms_tot = elemento(
        total,
        "ICMSTot"
    )

    totais = [
        ("vBC", "0.00"),
        ("vICMS", "0.00"),
        ("vICMSDeson", "0.00"),
        ("vFCP", "0.00"),
        ("vBCST", "0.00"),
        ("vST", "0.00"),
        ("vFCPST", "0.00"),
        ("vFCPSTRet", "0.00"),
        ("vProd", "1.00"),
        ("vFrete", "0.00"),
        ("vSeg", "0.00"),
        ("vDesc", "0.00"),
        ("vII", "0.00"),
        ("vIPI", "0.00"),
        ("vIPIDevol", "0.00"),
        ("vPIS", "0.00"),
        ("vCOFINS", "0.00"),
        ("vOutro", "0.00"),
        ("vNF", "1.00"),
        ("vTotTrib", "0.00"),
    ]

    for tag, valor in totais:

        elemento(
            icms_tot,
            tag,
            valor
        )

    # ========================================================
    # TRANSPORTE
    # ========================================================

    transp = elemento(
        inf_nfe,
        "transp"
    )

    elemento(
        transp,
        "modFrete",
        "9"
    )

    # ========================================================
    # PAGAMENTO
    # ========================================================

    pag = elemento(
        inf_nfe,
        "pag"
    )

    det_pag = elemento(
        pag,
        "detPag"
    )

    elemento(
        det_pag,
        "tPag",
        "01"
    )

    elemento(
        det_pag,
        "vPag",
        "1.00"
    )

    xml = etree.tostring(
        nfe,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False
    )

    titulo(
        "XML ANTES DA ASSINATURA"
    )

    print(
        xml.decode(
            "utf-8"
        )
    )

    return (
        xml,
        chave
    )


# ============================================================
# ASSINAR COM SIGNXML
# ============================================================

def assinar_com_signxml(
    xml,
    chave,
    private_key,
    certificate
):

    titulo(
        "[3] ASSINANDO XML NFC-e"
    )

    # A NF-e/NFC-e ainda exige XMLDSig com RSA-SHA1 e SHA1.
    # Versões atuais do SignXML bloqueiam a CRIAÇÃO de SHA1 por
    # política de segurança. Por isso, este teste monta a assinatura
    # XMLDSig diretamente com cryptography, seguindo o leiaute da NF-e.
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    import base64

    raiz = etree.fromstring(xml)

    inf_nfe = raiz.find(
        f"{{{NFE_NS}}}infNFe"
    )

    if inf_nfe is None:
        raise Exception("Tag infNFe não encontrada")

    id_inf = inf_nfe.get("Id")

    if id_inf != f"NFe{chave}":
        raise Exception(
            f"Id da infNFe inválido: {id_inf}"
        )

    # Canonicaliza a infNFe exatamente como exigido pelo XMLDSig.
    inf_c14n = etree.tostring(
        inf_nfe,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    digest = hashes.Hash(hashes.SHA1())
    digest.update(inf_c14n)
    digest_value = base64.b64encode(
        digest.finalize()
    ).decode("ascii")

    signature = etree.Element(
        etree.QName(DS_NS, "Signature"),
        nsmap={None: DS_NS}
    )

    signed_info = etree.SubElement(
        signature,
        etree.QName(DS_NS, "SignedInfo")
    )

    etree.SubElement(
        signed_info,
        etree.QName(DS_NS, "CanonicalizationMethod"),
        Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )

    etree.SubElement(
        signed_info,
        etree.QName(DS_NS, "SignatureMethod"),
        Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"
    )

    reference = etree.SubElement(
        signed_info,
        etree.QName(DS_NS, "Reference"),
        URI=f"#NFe{chave}"
    )

    transforms = etree.SubElement(
        reference,
        etree.QName(DS_NS, "Transforms")
    )

    etree.SubElement(
        transforms,
        etree.QName(DS_NS, "Transform"),
        Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"
    )

    etree.SubElement(
        transforms,
        etree.QName(DS_NS, "Transform"),
        Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )

    etree.SubElement(
        reference,
        etree.QName(DS_NS, "DigestMethod"),
        Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"
    )

    digest_node = etree.SubElement(
        reference,
        etree.QName(DS_NS, "DigestValue")
    )
    digest_node.text = digest_value

    signed_info_c14n = etree.tostring(
        signed_info,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    assinatura_bytes = private_key.sign(
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

    signature_value = etree.SubElement(
        signature,
        etree.QName(DS_NS, "SignatureValue")
    )
    signature_value.text = base64.b64encode(
        assinatura_bytes
    ).decode("ascii")

    key_info = etree.SubElement(
        signature,
        etree.QName(DS_NS, "KeyInfo")
    )

    x509_data = etree.SubElement(
        key_info,
        etree.QName(DS_NS, "X509Data")
    )

    x509_certificate = etree.SubElement(
        x509_data,
        etree.QName(DS_NS, "X509Certificate")
    )

    certificado_der = certificate.public_bytes(
        Encoding.DER
    )

    x509_certificate.text = base64.b64encode(
        certificado_der
    ).decode("ascii")

    # Signature deve ser filha direta de NFe, depois de infNFe.
    raiz.append(signature)

    xml_assinado = etree.tostring(
        raiz,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False
    )

    titulo(
        "XML ASSINADO"
    )

    print(
        xml_assinado.decode("utf-8")
    )

    log("")
    log(f"DigestValue: {digest_value}")
    log("[OK] XML assinado com RSA-SHA1 conforme leiaute NF-e/NFC-e.")

    return xml_assinado


# ============================================================
# VALIDAR ASSINATURA LOCALMENTE
# ============================================================

def validar_assinatura(
    xml_assinado,
    certificate
):

    titulo(
        "[4] VALIDANDO ASSINATURA LOCAL"
    )

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    import base64

    raiz = etree.fromstring(xml_assinado)

    inf_nfe = raiz.find(
        f"{{{NFE_NS}}}infNFe"
    )

    signature = raiz.find(
        f"{{{DS_NS}}}Signature"
    )

    if inf_nfe is None or signature is None:
        raise Exception("infNFe ou Signature não encontrada")

    signed_info = signature.find(
        f"{{{DS_NS}}}SignedInfo"
    )

    signature_value_node = signature.find(
        f"{{{DS_NS}}}SignatureValue"
    )

    reference = signed_info.find(
        f"{{{DS_NS}}}Reference"
    )

    digest_value_node = reference.find(
        f"{{{DS_NS}}}DigestValue"
    )

    # Recalcula o digest da infNFe. Como Signature é irmã da infNFe,
    # a transformação enveloped não remove nada dentro de infNFe.
    inf_c14n = etree.tostring(
        inf_nfe,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    digest = hashes.Hash(hashes.SHA1())
    digest.update(inf_c14n)
    digest_calculado = base64.b64encode(
        digest.finalize()
    ).decode("ascii")

    digest_xml = (digest_value_node.text or "").strip()

    if digest_calculado != digest_xml:
        raise Exception(
            "DigestValue inválido. "
            f"XML={digest_xml} calculado={digest_calculado}"
        )

    signed_info_c14n = etree.tostring(
        signed_info,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    assinatura = base64.b64decode(
        (signature_value_node.text or "").strip()
    )

    certificate.public_key().verify(
        assinatura,
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

    log("[OK] DigestValue confere.")
    log("[OK] SignatureValue validada com a chave pública do certificado.")
    log("[OK] ASSINATURA LOCAL VÁLIDA.")


# ============================================================
# GERAR PEM TLS
# ============================================================

def gerar_pem_tls(
    private_key,
    certificate,
    adicionais
):

    titulo(
        "[5] PREPARANDO CERTIFICADO TLS"
    )

    cert_pem = certificate.public_bytes(
        Encoding.PEM
    )

    for certificado in adicionais:

        cert_pem += certificado.public_bytes(
            Encoding.PEM
        )

    key_pem = private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        NoEncryption()
    )

    cert_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pem"
    )

    key_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pem"
    )

    cert_file.write(
        cert_pem
    )

    key_file.write(
        key_pem
    )

    cert_file.close()
    key_file.close()

    log(
        f"Cert PEM: {cert_file.name}"
    )

    log(
        f"Key PEM: {key_file.name}"
    )

    return (
        cert_file.name,
        key_file.name
    )


# ============================================================
# CRIAR ENVELOPE DE AUTORIZAÇÃO
# ============================================================

def criar_envi_nfe(
    xml_assinado
):

    titulo(
        "[6] CRIANDO ENVIAMENTO NFC-e"
    )

    nfe = etree.fromstring(
        xml_assinado
    )

    envi_nfe = etree.Element(
        etree.QName(
            NFE_NS,
            "enviNFe"
        ),
        nsmap={
            None: NFE_NS
        },
        versao="4.00"
    )

    elemento(
        envi_nfe,
        "idLote",
        str(
            random.randint(
                100000000000000,
                999999999999999
            )
        )
    )

    elemento(
        envi_nfe,
        "indSinc",
        "1"
    )

    envi_nfe.append(
        nfe
    )

    xml_envio = etree.tostring(
        envi_nfe,
        encoding="utf-8",
        xml_declaration=False,
        pretty_print=False
    )

    titulo(
        "enviNFe"
    )

    print(
        xml_envio.decode(
            "utf-8"
        )
    )

    return xml_envio


# ============================================================
# CRIAR SOAP
# ============================================================

def criar_soap(
    xml_envio
):

    xml_texto = xml_envio.decode(
        "utf-8"
    )

    soap = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap12:Envelope '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
        '<soap12:Body>'
        '<nfeDadosMsg '
        'xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">'
        f'{xml_texto}'
        '</nfeDadosMsg>'
        '</soap12:Body>'
        '</soap12:Envelope>'
    )

    return soap.encode(
        "utf-8"
    )


# ============================================================
# ENVIAR PARA SEFAZ
# ============================================================

def enviar_sefaz(
    xml_envio,
    cert_path,
    key_path
):

    titulo(
        "[7] ENVIANDO PARA SEFAZ-SP"
    )

    log(
        URL_SEFAZ
    )

    soap = criar_soap(
        xml_envio
    )

    log("")
    log(
        f"Bytes SOAP: {len(soap)}"
    )

    headers = {
        "Content-Type": (
            "application/soap+xml; "
            "charset=utf-8"
        )
    }

    response = requests.post(
        URL_SEFAZ,
        data=soap,
        headers=headers,
        cert=(
            cert_path,
            key_path
        ),

        # SOMENTE PARA ESTE DIAGNÓSTICO
        verify=False,

        timeout=60
    )

    titulo(
        "RESPOSTA SEFAZ"
    )

    log(
        f"HTTP STATUS: "
        f"{response.status_code}"
    )

    log("")

    log(
        "CONTENT-TYPE: "
        f"{response.headers.get('content-type')}"
    )

    log("")

    log("BODY:")
    log("")

    print(
        response.text
    )

    return response


# ============================================================
# ANALISAR RESPOSTA
# ============================================================

def analisar_resposta(
    response
):

    titulo(
        "[8] DIAGNÓSTICO"
    )

    texto = response.text

    try:

        raiz = etree.fromstring(
            texto.encode(
                "utf-8"
            )
        )

        cstats = raiz.xpath(
            "//*[local-name()='cStat']/text()"
        )

        motivos = raiz.xpath(
            "//*[local-name()='xMotivo']/text()"
        )

        if not cstats:

            log(
                "Nenhum cStat encontrado."
            )

            return

        log(
            "cStat encontrados:"
        )

        for indice, cstat in enumerate(
            cstats
        ):

            motivo = ""

            if indice < len(motivos):

                motivo = motivos[
                    indice
                ]

            log(
                f"{cstat} | {motivo}"
            )

        log("")

        if "100" in cstats:

            log(
                "[SUCESSO] NFC-e AUTORIZADA."
            )

            log("")
            log(
                "Isso seria uma evidência muito "
                "forte de problema na implementação "
                "anterior da assinatura."
            )

        elif "290" in cstats:

            log(
                "[RESULTADO IMPORTANTE]"
            )

            log("")
            log(
                "A SEFAZ também retornou 290 "
                "para uma assinatura criada "
                "independentemente pelo SignXML."
            )

            log("")
            log(
                "Nesse caso, o problema provavelmente "
                "NÃO está simplesmente na rotina "
                "manual de assinatura."
            )

        else:

            log(
                "[RESULTADO]"
            )

            log("")
            log(
                "A SEFAZ NÃO retornou 290."
            )

            log("")
            log(
                "Isso já é extremamente útil."
            )

            log("")
            log(
                "Leia o cStat acima. "
                "Se for uma rejeição fiscal, schema, "
                "IE, CSC, credenciamento ou outro "
                "campo da NFC-e, significa que a "
                "assinatura passou da etapa que "
                "antes retornava 290."
            )

    except Exception as e:

        log(
            "Não foi possível interpretar "
            "automaticamente a resposta."
        )

        log(
            str(e)
        )


# ============================================================
# MAIN
# ============================================================

def main():

    cert_path = None
    key_path = None

    titulo(
        "TESTE INDEPENDENTE NFC-e + SIGNXML + SEFAZ-SP"
    )

    try:

        # ====================================================
        # CERTIFICADO
        # ====================================================

        private_key, certificate, adicionais = (
            abrir_pfx()
        )

        # ====================================================
        # XML
        # ====================================================

        xml_base, chave = gerar_xml()

        # ====================================================
        # ASSINATURA INDEPENDENTE
        # ====================================================

        xml_assinado = assinar_com_signxml(
            xml_base,
            chave,
            private_key,
            certificate
        )

        # ====================================================
        # VALIDAÇÃO LOCAL
        # ====================================================

        validar_assinatura(
            xml_assinado,
            certificate
        )

        # ====================================================
        # CERTIFICADO TLS
        # ====================================================

        cert_path, key_path = gerar_pem_tls(
            private_key,
            certificate,
            adicionais
        )

        # ====================================================
        # ENVELOPE
        # ====================================================

        xml_envio = criar_envi_nfe(
            xml_assinado
        )

        # ====================================================
        # ENVIO
        # ====================================================

        response = enviar_sefaz(
            xml_envio,
            cert_path,
            key_path
        )

        # ====================================================
        # DIAGNÓSTICO
        # ====================================================

        analisar_resposta(
            response
        )

    except Exception as e:

        titulo(
            "ERRO NO TESTE"
        )

        log(
            type(e).__name__
        )

        log("")

        log(
            str(e)
        )

        import traceback

        log("")

        traceback.print_exc()

    finally:

        titulo(
            "LIMPEZA"
        )

        if (
            cert_path
            and
            os.path.exists(
                cert_path
            )
        ):

            os.remove(
                cert_path
            )

            log(
                "[OK] Certificado PEM removido."
            )

        if (
            key_path
            and
            os.path.exists(
                key_path
            )
        ):

            os.remove(
                key_path
            )

            log(
                "[OK] Chave PEM removida."
            )

        titulo(
            "FIM DO TESTE"
        )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    main()