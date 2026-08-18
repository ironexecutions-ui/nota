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
        cert_pem, key_pem = (
            _pfx_para_pem(
                certificado_path,
                certificado_senha
            )
        )

        # ==========================================
        # XML ASSINADO
        # ==========================================
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
        # ENVI NFE
        # ==========================================
        envi_nfe = f"""
<enviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">

<idLote>1</idLote>

<indSinc>1</indSinc>

{xml_str}

</enviNFe>
""".strip()

        # ==========================================
        # SOAP 1.2
        # ==========================================
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
        log("===== SOAP ENVIADO =====")

        log(soap[:10000])

        # ==========================================
        # ENVIO
        # ==========================================
        log("Enviando requisição")

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

        log(
            f"HTTP STATUS: "
            f"{response.status_code}"
        )

        log("===== RESPOSTA SEFAZ =====")

        log(response.text[:10000])

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

        log(f"cStat: {cStat}")

        log(f"xMotivo: {xMotivo}")

        # ==========================================
        # REJEIÇÃO
        # ==========================================
        if cStat != "100":

            raise Exception(
                f"NFC-e rejeitada: "
                f"{cStat} - {xMotivo}"
            )

        protocolo = retorno_xml.findtext(
            ".//nfe:nProt",
            namespaces=ns
        )

        chave = retorno_xml.findtext(
            ".//nfe:chNFe",
            namespaces=ns
        )

        log(f"CHAVE: {chave}")

        # ==========================================
        # QR CODE
        # ==========================================
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

        log("===== NFC-e AUTORIZADA =====")

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

        log("===== ERRO NFC-e =====")

        log(str(e))

        raise