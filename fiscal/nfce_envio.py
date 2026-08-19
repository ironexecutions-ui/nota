import requests
import urllib3

from lxml import etree

import hashlib
import base64
import tempfile
import os
import shutil

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
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


# ==========================================
# DESATIVA WARNING SSL
# ==========================================
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ==========================================
# NAMESPACES
# ==========================================
NFE_NS = "http://www.portalfiscal.inf.br/nfe"

SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"

WSDL_NS = (
    "http://www.portalfiscal.inf.br/nfe/"
    "wsdl/NFeAutorizacao4"
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

    if not certificado_path:
        raise Exception(
            "Caminho do certificado não informado"
        )

    if not os.path.exists(certificado_path):
        raise Exception(
            "Arquivo do certificado não encontrado"
        )

    with open(certificado_path, "rb") as f:
        pfx_data = f.read()

    log(
        f"Certificado PFX carregado: "
        f"{len(pfx_data)} bytes"
    )

    private_key, certificate, _ = (
        load_key_and_certificates(
            pfx_data,
            senha.encode(),
            backend=default_backend()
        )
    )

    if private_key is None:
        raise Exception(
            "Chave privada não encontrada no certificado"
        )

    if certificate is None:
        raise Exception(
            "Certificado digital não encontrado no PFX"
        )

    temp_dir = tempfile.mkdtemp(
        prefix="nfce_cert_"
    )

    cert_pem = os.path.join(
        temp_dir,
        "cert.pem"
    )

    key_pem = os.path.join(
        temp_dir,
        "key.pem"
    )

    with open(cert_pem, "wb") as f:
        f.write(
            certificate.public_bytes(
                Encoding.PEM
            )
        )

    with open(key_pem, "wb") as f:
        f.write(
            private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption()
            )
        )

    log("PEM gerado com sucesso")

    return cert_pem, key_pem, temp_dir


# ==========================================
# NORMALIZAR XML NFC-e
# ==========================================
def _normalizar_xml_nfce(
    xml_assinado
):

    log("Interpretando XML NFC-e assinado")

    if isinstance(xml_assinado, str):
        xml_bytes = xml_assinado.encode(
            "utf-8"
        )
    else:
        xml_bytes = xml_assinado

    try:
        raiz = etree.fromstring(
            xml_bytes
        )
    except Exception as e:
        raise Exception(
            f"XML NFC-e inválido: {e}"
        )

    nome_raiz = etree.QName(
        raiz
    ).localname

    namespace_raiz = etree.QName(
        raiz
    ).namespace

    log(
        f"Elemento raiz NFC-e: {nome_raiz}"
    )

    log(
        f"Namespace NFC-e: {namespace_raiz}"
    )

    if nome_raiz != "NFe":
        raise Exception(
            f"Elemento raiz esperado NFe, "
            f"recebido: {nome_raiz}"
        )

    if namespace_raiz != NFE_NS:
        raise Exception(
            "Namespace da NFC-e inválido. "
            f"Recebido: {namespace_raiz}"
        )

    inf_nfe = raiz.find(
        f"{{{NFE_NS}}}infNFe"
    )

    if inf_nfe is None:
        raise Exception(
            "Elemento infNFe não encontrado"
        )

    chave_id = inf_nfe.get("Id")

    if not chave_id:
        raise Exception(
            "Atributo Id do infNFe não encontrado"
        )

    log(
        f"infNFe encontrado: {chave_id}"
    )

    signature = raiz.find(
        "{http://www.w3.org/2000/09/xmldsig#}Signature"
    )

    if signature is None:
        raise Exception(
            "XML NFC-e não possui Signature"
        )

    log(
        "Signature encontrada como filha de NFe"
    )

    return raiz


# ==========================================
# VALIDAR ASSINATURA NO CONTEXTO ATUAL
# ==========================================
def _validar_assinatura_contexto(raiz, etapa):
    """
    Revalida DigestValue e SignatureValue no contexto XML atual.
    Isso detecta qualquer alteração causada ao inserir a NFe no lote
    ou no envelope SOAP antes do envio à SEFAZ.
    """

    DS_NS = "http://www.w3.org/2000/09/xmldsig#"

    log(f"Validando assinatura no contexto: {etapa}")

    nfe = raiz if etree.QName(raiz).localname == "NFe" else raiz.find(
        f".//{{{NFE_NS}}}NFe"
    )

    if nfe is None:
        raise Exception(f"NFe não encontrada durante validação: {etapa}")

    inf_nfe = nfe.find(f"{{{NFE_NS}}}infNFe")
    signature = nfe.find(f"{{{DS_NS}}}Signature")

    if inf_nfe is None or signature is None:
        raise Exception(f"Estrutura de assinatura incompleta: {etapa}")

    signed_info = signature.find(f"{{{DS_NS}}}SignedInfo")
    signature_value_el = signature.find(f"{{{DS_NS}}}SignatureValue")
    digest_value_el = signature.find(
        f"{{{DS_NS}}}SignedInfo/{{{DS_NS}}}Reference/{{{DS_NS}}}DigestValue"
    )
    cert_el = signature.find(
        f"{{{DS_NS}}}KeyInfo/{{{DS_NS}}}X509Data/{{{DS_NS}}}X509Certificate"
    )

    if any(x is None for x in (signed_info, signature_value_el, digest_value_el, cert_el)):
        raise Exception(f"Campos XMLDSig ausentes: {etapa}")

    inf_c14n = etree.tostring(
        inf_nfe,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    digest_calculado = base64.b64encode(
        hashlib.sha1(inf_c14n).digest()
    ).decode("ascii")

    digest_esperado = (digest_value_el.text or "").strip()

    log(f"[{etapa}] Digest esperado: {digest_esperado}")
    log(f"[{etapa}] Digest calculado: {digest_calculado}")

    if digest_calculado != digest_esperado:
        raise Exception(
            f"DigestValue foi alterado no contexto {etapa}. "
            f"Esperado={digest_esperado} Calculado={digest_calculado}"
        )

    signed_info_c14n = etree.tostring(
        signed_info,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    cert_der = base64.b64decode("".join((cert_el.text or "").split()))

    from cryptography import x509
    certificado_xml = x509.load_der_x509_certificate(cert_der)

    assinatura = base64.b64decode(
        "".join((signature_value_el.text or "").split())
    )

    try:
        certificado_xml.public_key().verify(
            assinatura,
            signed_info_c14n,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
    except Exception as e:
        raise Exception(
            f"SignatureValue inválido no contexto {etapa}: {e}"
        )

    log(f"[{etapa}] DigestValue válido")
    log(f"[{etapa}] SignatureValue válido")
    log(f"[{etapa}] ASSINATURA ÍNTEGRA")

    return True


# ==========================================
# REASSINAR XML NO CONTEXTO FINAL DO SOAP
# ==========================================
def _reassinar_no_contexto_soap(raiz, certificado_path, senha):
    """
    Recalcula DigestValue e SignatureValue depois que a NFC-e já está
    dentro do envelope SOAP. Assim, a assinatura é calculada usando
    exatamente o mesmo contexto de namespaces que será serializado
    e enviado à SEFAZ.
    """
    from cryptography import x509

    DS_NS = "http://www.w3.org/2000/09/xmldsig#"

    log("Reassinando NFC-e no contexto final do SOAP")

    nfe = raiz.find(f".//{{{NFE_NS}}}NFe")
    if nfe is None:
        raise Exception("NFe não encontrada dentro do SOAP para reassinatura")

    inf_nfe = nfe.find(f"{{{NFE_NS}}}infNFe")
    signature = nfe.find(f"{{{DS_NS}}}Signature")

    if inf_nfe is None or signature is None:
        raise Exception("Estrutura da assinatura incompleta dentro do SOAP")

    signed_info = signature.find(f"{{{DS_NS}}}SignedInfo")
    signature_value_el = signature.find(f"{{{DS_NS}}}SignatureValue")
    digest_value_el = signature.find(
        f"{{{DS_NS}}}SignedInfo/{{{DS_NS}}}Reference/{{{DS_NS}}}DigestValue"
    )
    cert_el = signature.find(
        f"{{{DS_NS}}}KeyInfo/{{{DS_NS}}}X509Data/{{{DS_NS}}}X509Certificate"
    )

    if any(x is None for x in (signed_info, signature_value_el, digest_value_el, cert_el)):
        raise Exception("Campos XMLDSig ausentes durante reassinatura no SOAP")

    with open(certificado_path, "rb") as f:
        pfx_data = f.read()

    private_key, certificate, _ = load_key_and_certificates(
        pfx_data,
        senha.encode(),
        backend=default_backend()
    )

    if private_key is None or certificate is None:
        raise Exception("PFX sem chave privada ou certificado para reassinatura")

    # Garante que o certificado presente no XML continua sendo o do PFX.
    cert_der_xml = base64.b64decode("".join((cert_el.text or "").split()))
    cert_der_pfx = certificate.public_bytes(Encoding.DER)

    if cert_der_xml != cert_der_pfx:
        raise Exception("Certificado do XML difere do PFX antes da reassinatura")

    # 1. Digest da infNFe no contexto final do SOAP.
    inf_c14n = etree.tostring(
        inf_nfe,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    digest_final = base64.b64encode(
        hashlib.sha1(inf_c14n).digest()
    ).decode("ascii")

    digest_value_el.text = digest_final
    log(f"DigestValue recalculado no SOAP: {digest_final}")

    # 2. Como DigestValue faz parte de SignedInfo, canonicaliza SignedInfo
    # novamente e gera um novo SignatureValue.
    signed_info_c14n = etree.tostring(
        signed_info,
        method="c14n",
        exclusive=False,
        with_comments=False
    )

    assinatura = private_key.sign(
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

    signature_value_el.text = base64.b64encode(assinatura).decode("ascii")
    log("SignatureValue recalculado no contexto final do SOAP")

    # 3. Verificação matemática imediata com a chave pública do certificado.
    certificate.public_key().verify(
        assinatura,
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

    log("Reassinatura no contexto SOAP validada matematicamente")
    return raiz


# ==========================================
# MONTAR LOTE enviNFe
# ==========================================
def _montar_envi_nfe(
    nfe_element
):

    log("Montando enviNFe com lxml")

    envi_nfe = etree.Element(
        etree.QName(
            NFE_NS,
            "enviNFe"
        ),
        nsmap={
            None: NFE_NS
        }
    )

    envi_nfe.set(
        "versao",
        "4.00"
    )

    id_lote = etree.SubElement(
        envi_nfe,
        etree.QName(
            NFE_NS,
            "idLote"
        )
    )

    id_lote.text = "1"

    ind_sinc = etree.SubElement(
        envi_nfe,
        etree.QName(
            NFE_NS,
            "indSinc"
        )
    )

    ind_sinc.text = "1"

    # IMPORTANTE:
    # não convertemos NFe para string
    # para depois concatenar.
    #
    # O elemento XML real é inserido
    # diretamente dentro do enviNFe.
    envi_nfe.append(
        nfe_element
    )

    log(
        "NFe adicionada ao lote como elemento XML"
    )

    return envi_nfe


# ==========================================
# MONTAR SOAP
# ==========================================
def _montar_soap(
    envi_nfe
):

    log("Montando SOAP 1.2 com lxml")

    envelope = etree.Element(
        etree.QName(
            SOAP_NS,
            "Envelope"
        ),
        nsmap={
            "soap12": SOAP_NS,
            "xsi":
                "http://www.w3.org/2001/XMLSchema-instance",
            "xsd":
                "http://www.w3.org/2001/XMLSchema"
        }
    )

    header = etree.SubElement(
        envelope,
        etree.QName(
            SOAP_NS,
            "Header"
        )
    )

    cabecalho = etree.SubElement(
        header,
        etree.QName(
            WSDL_NS,
            "nfeCabecMsg"
        ),
        nsmap={
            None: WSDL_NS
        }
    )

    cuf = etree.SubElement(
        cabecalho,
        etree.QName(
            WSDL_NS,
            "cUF"
        )
    )

    cuf.text = "35"

    versao_dados = etree.SubElement(
        cabecalho,
        etree.QName(
            WSDL_NS,
            "versaoDados"
        )
    )

    versao_dados.text = "4.00"

    body = etree.SubElement(
        envelope,
        etree.QName(
            SOAP_NS,
            "Body"
        )
    )

    dados_msg = etree.SubElement(
        body,
        etree.QName(
            WSDL_NS,
            "nfeDadosMsg"
        ),
        nsmap={
            None: WSDL_NS
        }
    )

    # O enviNFe entra como XML real.
    dados_msg.append(
        envi_nfe
    )

    log(
        "enviNFe inserido dentro de nfeDadosMsg"
    )

    return envelope


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

    log(
        "===== INÍCIO ENVIO NFC-e ====="
    )

    temp_dir = None

    try:

        # ==========================================
        # AMBIENTE
        # ==========================================
        ambiente = str(
            ambiente
        ).strip().lower()

        log(
            f"Ambiente recebido: {ambiente}"
        )

        url = URLS_SP.get(
            ambiente
        )

        if not url:
            raise Exception(
                f"Ambiente inválido: {ambiente}"
            )

        log(
            f"URL SEFAZ: {url}"
        )

        # ==========================================
        # CERTIFICADO
        # ==========================================
        log(
            "Preparando certificado"
        )

        cert_pem, key_pem, temp_dir = (
            _pfx_para_pem(
                certificado_path,
                certificado_senha
            )
        )

        # ==========================================
        # XML NFC-e
        # ==========================================
        log(
            "Validando XML assinado"
        )

        nfe_element = (
            _normalizar_xml_nfce(
                xml_assinado
            )
        )

        print("\n")
        print("=" * 100)
        print(
            "================ NFC-e ASSINADA ================"
        )
        print("=" * 100)

        print(
            etree.tostring(
                nfe_element,
                encoding="unicode",
                pretty_print=True
            )
        )

        print("=" * 100)
        print("\n")

        # ==========================================
        # LOTE
        # ==========================================
        envi_nfe = _montar_envi_nfe(
            nfe_element
        )

        # Revalida depois de inserir a NFe no enviNFe.
        # Se o contexto de namespaces alterar a assinatura,
        # o envio é interrompido aqui antes de chegar à SEFAZ.
        _validar_assinatura_contexto(
            envi_nfe,
            "APOS_INSERIR_NO_LOTE"
        )

        lote_bytes = etree.tostring(
            envi_nfe,
            encoding="utf-8",
            xml_declaration=False
        )

        log(
            "Validando XML do lote"
        )

        etree.fromstring(
            lote_bytes
        )

        log(
            "XML do lote possui sintaxe válida"
        )

        print("\n")
        print("=" * 100)
        print(
            "================ LOTE enviNFe ================"
        )
        print("=" * 100)

        print(
            lote_bytes.decode(
                "utf-8"
            )
        )

        print("=" * 100)
        print("\n")

        # ==========================================
        # SOAP
        # ==========================================
        soap_element = _montar_soap(
            envi_nfe
        )

        # A canonicalização inclusiva usada pela NFC-e passa a enxergar
        # os namespaces ancestrais do SOAP. Por isso recalculamos o Digest
        # e o SignatureValue somente depois de montar o envelope final.
        _reassinar_no_contexto_soap(
            soap_element,
            certificado_path,
            certificado_senha
        )

        # Agora a assinatura precisa obrigatoriamente permanecer íntegra
        # no contexto exato que será serializado e enviado.
        _validar_assinatura_contexto(
            soap_element,
            "DENTRO_DO_SOAP_APOS_REASSINATURA"
        )

        soap_bytes = etree.tostring(
            soap_element,
            encoding="utf-8",
            xml_declaration=True
        )

        log(
            "Validando XML SOAP"
        )

        etree.fromstring(
            soap_bytes
        )

        log(
            "SOAP possui sintaxe XML válida"
        )

        print("\n")
        print("=" * 100)
        print(
            "================ SOAP ENVIADO ================"
        )
        print("=" * 100)

        print(
            soap_bytes.decode(
                "utf-8"
            )
        )

        print("=" * 100)
        print("\n")

        # ==========================================
        # HEADERS
        # ==========================================
        headers = {
            "Content-Type":
                "application/soap+xml; charset=utf-8"
        }

        # ==========================================
        # ENVIO
        # ==========================================
        log(
            "Enviando requisição para SEFAZ"
        )

        response = requests.post(
            url,
            data=soap_bytes,
            headers=headers,
            cert=(
                cert_pem,
                key_pem
            ),
            verify=False,
            timeout=120
        )

        # ==========================================
        # RESPOSTA
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
            "================ RESPOSTA SEFAZ ================"
        )
        print("=" * 100)

        print(
            response.text
        )

        print("=" * 100)
        print("\n")

        if response.status_code != 200:

            raise Exception(
                f"Erro HTTP SEFAZ: "
                f"{response.status_code} | "
                f"{response.text[:3000]}"
            )

        # ==========================================
        # PARSE RESPOSTA
        # ==========================================
        log(
            "Interpretando retorno SEFAZ"
        )

        try:

            retorno_xml = etree.fromstring(
                response.content
            )

        except Exception as e:

            raise Exception(
                f"Resposta da SEFAZ não é XML válido: {e}"
            )
        ns = {
            "nfe": NFE_NS
        }

        # ==========================================
        # STATUS DO LOTE
        # ==========================================
        ret_envi = retorno_xml.find(
            ".//nfe:retEnviNFe",
            namespaces=ns
        )

        if ret_envi is None:
            raise Exception(
                "SEFAZ não retornou retEnviNFe. "
                f"Resposta: {response.text[:3000]}"
            )

        cstat_lote = ret_envi.findtext(
            "nfe:cStat",
            namespaces=ns
        )

        motivo_lote = ret_envi.findtext(
            "nfe:xMotivo",
            namespaces=ns
        )

        log(
            f"cStat DO LOTE: [{cstat_lote}]"
        )

        log(
            f"xMotivo DO LOTE: [{motivo_lote}]"
        )

        if cstat_lote is None:
            raise Exception(
                "SEFAZ não retornou cStat do lote"
            )

        # ==========================================
        # 104 = LOTE PROCESSADO
        # ==========================================
        if cstat_lote != "104":

            print("\n")
            print("!" * 100)
            print(
                "================ LOTE NFC-e REJEITADO ================"
            )
            print("!" * 100)

            print(
                f"cStat lote: {cstat_lote}"
            )

            print(
                f"xMotivo lote: {motivo_lote}"
            )

            print("!" * 100)
            print("\n")

            raise Exception(
                f"Lote NFC-e rejeitado: "
                f"{cstat_lote} - {motivo_lote}"
            )

        log(
            "Lote processado pela SEFAZ com sucesso"
        )

        # ==========================================
        # PROTOCOLO DA NFC-e
        # ==========================================
        inf_prot = retorno_xml.find(
            ".//nfe:protNFe/nfe:infProt",
            namespaces=ns
        )

        if inf_prot is None:
            raise Exception(
                "Lote processado, mas infProt "
                "não foi encontrado na resposta da SEFAZ"
            )

        cstat_nfce = inf_prot.findtext(
            "nfe:cStat",
            namespaces=ns
        )

        motivo_nfce = inf_prot.findtext(
            "nfe:xMotivo",
            namespaces=ns
        )

        chave = inf_prot.findtext(
            "nfe:chNFe",
            namespaces=ns
        )

        protocolo = inf_prot.findtext(
            "nfe:nProt",
            namespaces=ns
        )

        log(
            f"cStat DA NFC-e: [{cstat_nfce}]"
        )

        log(
            f"xMotivo DA NFC-e: [{motivo_nfce}]"
        )

        log(
            f"CHAVE RETORNADA: [{chave}]"
        )

        log(
            f"PROTOCOLO RETORNADO: [{protocolo}]"
        )

        if cstat_nfce is None:
            raise Exception(
                "SEFAZ não retornou o cStat "
                "individual da NFC-e"
            )

        # ==========================================
        # 100 = NFC-e AUTORIZADA
        # ==========================================
        if cstat_nfce != "100":

            print("\n")
            print("!" * 100)
            print(
                "================ NFC-e REJEITADA ================"
            )
            print("!" * 100)

            print(
                f"cStat: {cstat_nfce}"
            )

            print(
                f"xMotivo: {motivo_nfce}"
            )

            if chave:
                print(
                    f"Chave: {chave}"
                )

            print("!" * 100)
            print("\n")

            raise Exception(
                f"NFC-e rejeitada: "
                f"{cstat_nfce} - {motivo_nfce}"
            )

        # ==========================================
        # NFC-e AUTORIZADA
        # ==========================================
        if not protocolo:
            raise Exception(
                "NFC-e autorizada com cStat 100, "
                "mas protocolo não foi encontrado"
            )

        if not chave:
            raise Exception(
                "NFC-e autorizada com cStat 100, "
                "mas chave não foi encontrada"
            )

        log(
            "NFC-e AUTORIZADA PELA SEFAZ"
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
        #
        # Mantive essa parte compatível com o
        # comportamento atual do seu sistema.
        #
        # Depois que resolvermos a autorização,
        # revisamos o QR Code separadamente.
        # ==========================================

        log(
            "Gerando URL do QR Code"
        )

        qr_base = (
            f"chNFe={chave}"
            f"&nVersao=100"
            f"&tpAmb="
            f"{'2' if ambiente == 'homologacao' else '1'}"
            f"&vNF={float(total_nf):.2f}"
            f"&cIdToken={fiscal['csc_id']}"
        )

        hash_qr = hashlib.sha1(
            (
                qr_base +
                str(
                    fiscal["csc_token"]
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        qr_code_url = (
            "https://www.sefaz.sp.gov.br/NFCE/qrcode?"
            + qr_base
            + f"&cHashQRCode={hash_qr}"
        )

        log(
            f"QR CODE URL: {qr_code_url}"
        )

        # ==========================================
        # AUTORIZADA
        # ==========================================
        print("\n")
        print("=" * 100)
        print(
            "================ NFC-e AUTORIZADA ================"
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
            "================ ERRO NO ENVIO NFC-e ================"
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

        log(
            "===== ERRO NFC-e ====="
        )

        log(
            str(e)
        )

        raise

    finally:

        # ==========================================
        # LIMPEZA DOS PEM TEMPORÁRIOS
        # ==========================================
        if temp_dir:

            try:

                shutil.rmtree(
                    temp_dir,
                    ignore_errors=True
                )

                log(
                    "Arquivos PEM temporários removidos"
                )

            except Exception as cleanup_error:

                log(
                    f"Erro limpando PEM temporário: "
                    f"{cleanup_error}"
                )