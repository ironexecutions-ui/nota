import requests
import urllib3

from lxml import etree

import hashlib
import base64
import tempfile
import os

from datetime import datetime

# ==========================================
# CRYPTOGRAPHY
# ==========================================
from cryptography.hazmat.primitives.serialization.pkcs12 import (
    load_key_and_certificates
)

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    NoEncryption
)

from cryptography.hazmat.backends import default_backend


# ==========================================
# DESATIVA WARNING SSL
# ==========================================
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


def log(msg):

    print(
        f"[NFCe-ENVIO]"
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{msg}"
    )


# ==========================================
# URLS SEFAZ SP
# ==========================================
URLS_SP = {

    "homologacao":
        "https://homologacao.nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4.asmx",

    "producao":
        "https://nfce.fazenda.sp.gov.br/ws/NFeAutorizacao4.asmx"
}


# ==========================================
# PFX → PEM
# ==========================================
def _pfx_para_pem(
    certificado_path,
    senha
):

    log("Convertendo PFX para PEM")

    if not os.path.exists(
        certificado_path
    ):

        raise Exception(
            "Arquivo do certificado "
            "não encontrado"
        )

    with open(
        certificado_path,
        "rb"
    ) as f:

        pfx_data = f.read()

    # ==========================================
    # LOAD CERTIFICADO
    # ==========================================
    private_key, certificate, _ = (

        load_key_and_certificates(

            pfx_data,

            senha.encode(),

            backend=default_backend()
        )
    )

    if not private_key or not certificate:

        raise Exception(
            "Certificado inválido "
            "ou senha incorreta"
        )

    temp_dir = tempfile.mkdtemp()

    cert_pem = os.path.join(
        temp_dir,
        "cert.pem"
    )

    key_pem = os.path.join(
        temp_dir,
        "key.pem"
    )

    # ==========================================
    # CERTIFICADO PEM
    # ==========================================
    with open(
        cert_pem,
        "wb"
    ) as f:

        f.write(

            certificate.public_bytes(
                Encoding.PEM
            )
        )

    # ==========================================
    # CHAVE PRIVADA PEM
    # ==========================================
    with open(
        key_pem,
        "wb"
    ) as f:

        f.write(

            private_key.private_bytes(

                Encoding.PEM,

                PrivateFormat.TraditionalOpenSSL,

                NoEncryption()
            )
        )

    log("PEM gerado com sucesso")

    return cert_pem, key_pem


# ==========================================
# ENVIO NFC-e
# ==========================================
def enviar_nfce(
    xml_assinado,
    ambiente,
    certificado_path,
    certificado_senha,
    fiscal,
    total_nf
):

    log("===== INÍCIO ENVIO NFC-e =====")

    try:

        # ==========================================
        # URL
        # ==========================================
        url = URLS_SP.get(
            ambiente
        )

        if not url:

            raise Exception(
                "Ambiente inválido"
            )

        log(f"URL: {url}")

        # ==========================================
        # CERTIFICADO
        # ==========================================
        log("Preparando certificado para comunicação com SEFAZ")

        cert_pem, key_pem = (
            _pfx_para_pem(
                certificado_path,
                certificado_senha
            )
        )

        log("Certificado preparado")

        # ==========================================
        # XML ASSINADO
        # ==========================================
        log("Convertendo XML assinado para string")

        xml_str = xml_assinado.decode(
            "utf-8"
        )

        # ==========================================
        # REMOVE XML DECLARATION
        # ==========================================
        xml_str = xml_str.replace(
            '<?xml version="1.0" encoding="utf-8"?>',
            ""
        )

        xml_str = xml_str.replace(
            "<?xml version='1.0' encoding='utf-8'?>",
            ""
        )

        xml_str = xml_str.strip()

        # ==========================================
        # DEBUG XML NFC-e
        # ==========================================
        print("\n")
        print("=" * 100)
        print(
            "================ XML NFC-e ASSINADO "
            "ANTES DO enviNFe ================"
        )
        print("=" * 100)

        print(xml_str)

        print("=" * 100)
        print(
            "================ FIM XML NFC-e "
            "ASSINADO ============================="
        )
        print("=" * 100)
        print("\n")

        # ==========================================
        # TENTA VALIDAR SINTAXE XML
        # ==========================================
        log("Validando sintaxe do XML assinado")

        try:

            etree.fromstring(
                xml_str.encode("utf-8")
            )

            log(
                "XML assinado possui sintaxe XML válida"
            )

        except Exception as xml_error:

            log(
                "ERRO DE SINTAXE NO XML ASSINADO"
            )

            log(str(xml_error))

            raise

        # ==========================================
        # ENVI NFE
        # ==========================================
        log("Montando lote enviNFe")

        envi_nfe = f"""
<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">

<idLote>1</idLote>

<indSinc>1</indSinc>

{xml_str}

</enviNFe>
""".strip()

        # ==========================================
        # DEBUG LOTE
        # ==========================================
        print("\n")
        print("=" * 100)
        print(
            "================ XML DO LOTE enviNFe "
            "================"
        )
        print("=" * 100)

        print(envi_nfe)

        print("=" * 100)
        print(
            "================ FIM DO LOTE enviNFe "
            "================="
        )
        print("=" * 100)
        print("\n")

        # ==========================================
        # VALIDA SINTAXE DO LOTE
        # ==========================================
        log("Validando sintaxe XML do lote enviNFe")

        try:

            etree.fromstring(
                envi_nfe.encode("utf-8")
            )

            log(
                "Lote enviNFe possui sintaxe XML válida"
            )

        except Exception as lote_error:

            log(
                "ERRO DE SINTAXE NO LOTE enviNFe"
            )

            log(str(lote_error))

            raise

        # ==========================================
        # SOAP 1.2
        # ==========================================
        log("Montando envelope SOAP 1.2")

        soap = f"""
<soap12:Envelope
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xmlns:xsd="http://www.w3.org/2001/XMLSchema"
xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">

<soap12:Header>

<nfeCabecMsg
xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">

<cUF>35</cUF>

<versaoDados>4.00</versaoDados>

</nfeCabecMsg>

</soap12:Header>

<soap12:Body>

<nfeDadosMsg
xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">

{envi_nfe}

</nfeDadosMsg>

</soap12:Body>

</soap12:Envelope>
""".strip()

        headers = {

            "Content-Type":
                "application/soap+xml; charset=utf-8"
        }

        # ==========================================
        # DEBUG SOAP
        # ==========================================
        print("\n")
        print("=" * 100)
        print(
            "================ SOAP COMPLETO ENVIADO "
            "À SEFAZ ================"
        )
        print("=" * 100)

        print(soap)

        print("=" * 100)
        print(
            "================ FIM SOAP "
            "================"
        )
        print("=" * 100)
        print("\n")

        # ==========================================
        # VALIDA SINTAXE SOAP
        # ==========================================
        log("Validando sintaxe XML do SOAP")

        try:

            etree.fromstring(
                soap.encode("utf-8")
            )

            log(
                "SOAP possui sintaxe XML válida"
            )

        except Exception as soap_error:

            log(
                "ERRO DE SINTAXE NO SOAP"
            )

            log(str(soap_error))

            raise

        # ==========================================
        # ENVIO
        # ==========================================
        log("Enviando requisição para SEFAZ")

        response = requests.post(

            url,

            data=soap.encode(
                "utf-8"
            ),

            headers=headers,

            cert=(
                cert_pem,
                key_pem
            ),

            verify=False,

            timeout=120
        )

        # ==========================================
        # RESPOSTA HTTP
        # ==========================================
        log(
            f"HTTP STATUS: "
            f"{response.status_code}"
        )

        log(
            f"CONTENT-TYPE: "
            f"{response.headers.get('content-type')}"
        )

        print("\n")
        print("=" * 100)
        print(
            "================ RESPOSTA COMPLETA "
            "SEFAZ ================"
        )
        print("=" * 100)

        print(response.text)

        print("=" * 100)
        print(
            "================ FIM RESPOSTA "
            "SEFAZ ================"
        )
        print("=" * 100)
        print("\n")

        # ==========================================
        # ERRO HTTP
        # ==========================================
        if response.status_code != 200:

            raise Exception(
                f"Erro HTTP SEFAZ: "
                f"{response.status_code} | "
                f"{response.text[:3000]}"
            )

        # ==========================================
        # XML RETORNO
        # ==========================================
        log("Interpretando XML retornado pela SEFAZ")

        retorno_xml = etree.fromstring(
            response.content
        )

        ns = {

            "nfe":
                "http://www.portalfiscal.inf.br/nfe"
        }

        cStat = retorno_xml.findtext(
            ".//nfe:cStat",
            namespaces=ns
        )

        xMotivo = retorno_xml.findtext(
            ".//nfe:xMotivo",
            namespaces=ns
        )

        log(
            f"cStat recebido: [{cStat}]"
        )

        log(
            f"xMotivo recebido: [{xMotivo}]"
        )

        # ==========================================
        # REJEIÇÃO
        # ==========================================
        if cStat != "100":

            print("\n")
            print("!" * 100)
            print(
                "================ NFC-e REJEITADA "
                "================"
            )
            print("!" * 100)

            print(
                f"cStat: {cStat}"
            )

            print(
                f"xMotivo: {xMotivo}"
            )

            print("!" * 100)
            print("\n")

            raise Exception(
                f"NFC-e rejeitada: "
                f"{cStat} - {xMotivo}"
            )

        # ==========================================
        # PROTOCOLO
        # ==========================================
        protocolo = retorno_xml.findtext(
            ".//nfe:nProt",
            namespaces=ns
        )

        chave = retorno_xml.findtext(
            ".//nfe:chNFe",
            namespaces=ns
        )

        log(
            f"PROTOCOLO: {protocolo}"
        )

        log(
            f"CHAVE: {chave}"
        )

        # ==========================================
        # QR CODE
        # ==========================================
        log("Gerando QR Code da NFC-e")

        qr_base = (

            f"chNFe={chave}"
            f"&nVersao=100"
            f"&tpAmb={'2' if ambiente == 'homologacao' else '1'}"
            f"&vNF={total_nf:.2f}"
            f"&cIdToken={fiscal['csc_id']}"
        )

        hash_qr = hashlib.sha1(

            (
                qr_base +
                fiscal["csc_token"]
            ).encode()

        ).digest()

        hash_b64 = (
            base64.b64encode(
                hash_qr
            ).decode()
        )

        qr_code_url = (

            "https://www.sefaz.sp.gov.br/NFCE/qrcode?"
            + qr_base +
            f"&cHashQRCode={hash_b64}"
        )

        log(
            f"QR CODE URL: {qr_code_url}"
        )

        print("\n")
        print("=" * 100)
        print(
            "================ NFC-e AUTORIZADA "
            "================"
        )
        print("=" * 100)

        print(
            f"CHAVE: {chave}"
        )

        print(
            f"PROTOCOLO: {protocolo}"
        )

        print("=" * 100)
        print("\n")

        return {

            "status": "autorizada",

            "numero": int(
                chave[25:34]
            ),

            "serie": int(
                chave[22:25]
            ),

            "chave": chave,

            "qr_code": qr_code_url,

            "protocolo": protocolo
        }

    except Exception as e:

        print("\n")
        print("!" * 100)
        print(
            "================ ERRO NO ENVIO NFC-e "
            "================"
        )
        print("!" * 100)

        print(
            f"TIPO: {type(e).__name__}"
        )

        print(
            f"MENSAGEM: {str(e)}"
        )

        print(
            f"REPR: {repr(e)}"
        )

        print("!" * 100)
        print("\n")

        log("===== ERRO NFC-e =====")

        log(str(e))

        raise