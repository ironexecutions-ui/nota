from datetime import datetime

import base64
import hashlib

from lxml import etree

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding
)

from cryptography.hazmat.primitives import hashes

from cryptography.hazmat.primitives.asymmetric import padding

from cryptography.hazmat.backends import default_backend


# ============================================================
# NAMESPACES
# ============================================================

NAMESPACE_NFE = "http://www.portalfiscal.inf.br/nfe"
NAMESPACE_DS = "http://www.w3.org/2000/09/xmldsig#"

C14N_ALGORITHM = (
    "http://www.w3.org/TR/"
    "2001/REC-xml-c14n-20010315"
)

SIGNATURE_ALGORITHM = (
    "http://www.w3.org/2000/09/"
    "xmldsig#rsa-sha1"
)

DIGEST_ALGORITHM = (
    "http://www.w3.org/2000/09/"
    "xmldsig#sha1"
)

ENVELOPED_ALGORITHM = (
    "http://www.w3.org/2000/09/"
    "xmldsig#enveloped-signature"
)


# ============================================================
# LOG
# ============================================================

def log(msg):

    print(
        f"[NFCe-ASSINATURA]"
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{msg}"
    )


# ============================================================
# CANONICALIZA XML
# ============================================================

def canonicalizar(elemento):

    return etree.tostring(
        elemento,
        method="c14n",
        exclusive=False,
        with_comments=False
    )


# ============================================================
# ASSINA XML NFC-e
# ============================================================

def assinar_xml(
    xml_bytes,
    certificado_path,
    senha
):

    """
    Assina o infNFe da NFC-e utilizando:

    XMLDSig Enveloped
    RSA-SHA1
    SHA1
    C14N 1.0

    Estrutura final:

    <NFe>
        <infNFe>
            ...
        </infNFe>

        <Signature>
            ...
        </Signature>
    </NFe>
    """

    log("===== INÍCIO ASSINATURA XML =====")

    try:

        # ====================================================
        # 1. CERTIFICADO
        # ====================================================

        log("ETAPA 1: Lendo certificado A1")

        if not certificado_path:

            raise Exception(
                "Caminho do certificado não informado"
            )

        with open(certificado_path, "rb") as f:

            pfx_data = f.read()

        log(
            f"Certificado carregado do disco | "
            f"{len(pfx_data)} bytes"
        )

        # ====================================================
        # 2. ABRE PFX
        # ====================================================

        log("ETAPA 2: Abrindo certificado PFX")

        (
            private_key,
            certificate,
            additional_certificates
        ) = pkcs12.load_key_and_certificates(

            pfx_data,

            senha.encode(),

            backend=default_backend()
        )

        if private_key is None:

            raise Exception(
                "Chave privada não encontrada "
                "no certificado"
            )

        if certificate is None:

            raise Exception(
                "Certificado não encontrado "
                "no arquivo PFX"
            )

        log("Chave privada encontrada")

        log("Certificado encontrado")

        if additional_certificates:

            log(
                f"Certificados adicionais encontrados: "
                f"{len(additional_certificates)}"
            )

            log(
                "Eles NÃO serão incluídos na assinatura"
            )

        else:

            log(
                "Nenhum certificado adicional será enviado"
            )

        # ====================================================
        # 3. PREPARA XML
        # ====================================================

        log("ETAPA 3: Preparando XML")

        if isinstance(xml_bytes, str):

            xml_bytes = xml_bytes.encode(
                "utf-8"
            )

        parser = etree.XMLParser(

            remove_blank_text=True,

            resolve_entities=False
        )

        xml = etree.fromstring(

            xml_bytes,

            parser=parser
        )

        log(
            f"Elemento raiz recebido: "
            f"{xml.tag}"
        )

        # ====================================================
        # 4. LOCALIZA infNFe
        # ====================================================

        log("ETAPA 4: Procurando infNFe")

        infNFe = xml.find(

            f".//{{{NAMESPACE_NFE}}}infNFe"
        )

        if infNFe is None:

            raise Exception(
                "Nó <infNFe> não encontrado no XML"
            )

        infNFe_id = infNFe.get("Id")

        if not infNFe_id:

            raise Exception(
                "Atributo Id do <infNFe> "
                "não encontrado"
            )

        if not infNFe_id.startswith("NFe"):

            raise Exception(
                f"Id do infNFe inválido: "
                f"{infNFe_id}"
            )

        log(
            f"infNFe encontrado com Id: "
            f"{infNFe_id}"
        )

        # ====================================================
        # 5. CONFERE ASSINATURA EXISTENTE
        # ====================================================

        log(
            "ETAPA 5: Verificando assinatura existente"
        )

        assinatura_existente = xml.find(

            f".//{{{NAMESPACE_DS}}}Signature"
        )

        if assinatura_existente is not None:

            raise Exception(
                "XML já possui assinatura digital"
            )

        log(
            "XML ainda não possui assinatura"
        )

        # ====================================================
        # 6. CANONICALIZA infNFe
        # ====================================================

        log(
            "ETAPA 6: Canonicalizando infNFe"
        )

        infNFe_c14n = canonicalizar(
            infNFe
        )

        log(
            f"infNFe canonicalizado | "
            f"{len(infNFe_c14n)} bytes"
        )

        # ====================================================
        # 7. DIGEST SHA1
        # ====================================================

        log(
            "ETAPA 7: Calculando DigestValue SHA1"
        )

        digest = hashlib.sha1(
            infNFe_c14n
        ).digest()

        digest_value = base64.b64encode(
            digest
        ).decode("ascii")

        log(
            f"DigestValue: {digest_value}"
        )

        # ====================================================
        # 8. CRIA SIGNATURE
        # ====================================================

        log(
            "ETAPA 8: Criando estrutura Signature"
        )

        signature = etree.Element(

            etree.QName(
                NAMESPACE_DS,
                "Signature"
            ),

            nsmap={
                None: NAMESPACE_DS
            }
        )

        # ====================================================
        # SignedInfo
        # ====================================================

        signed_info = etree.SubElement(

            signature,

            etree.QName(
                NAMESPACE_DS,
                "SignedInfo"
            )
        )

        # ====================================================
        # CanonicalizationMethod
        # ====================================================

        canonicalization_method = etree.SubElement(

            signed_info,

            etree.QName(
                NAMESPACE_DS,
                "CanonicalizationMethod"
            )
        )

        canonicalization_method.set(

            "Algorithm",

            C14N_ALGORITHM
        )

        # ====================================================
        # SignatureMethod
        # ====================================================

        signature_method = etree.SubElement(

            signed_info,

            etree.QName(
                NAMESPACE_DS,
                "SignatureMethod"
            )
        )

        signature_method.set(

            "Algorithm",

            SIGNATURE_ALGORITHM
        )

        # ====================================================
        # Reference
        # ====================================================

        reference = etree.SubElement(

            signed_info,

            etree.QName(
                NAMESPACE_DS,
                "Reference"
            )
        )

        reference.set(

            "URI",

            f"#{infNFe_id}"
        )

        # ====================================================
        # Transforms
        # ====================================================

        transforms = etree.SubElement(

            reference,

            etree.QName(
                NAMESPACE_DS,
                "Transforms"
            )
        )

        transform_enveloped = etree.SubElement(

            transforms,

            etree.QName(
                NAMESPACE_DS,
                "Transform"
            )
        )

        transform_enveloped.set(

            "Algorithm",

            ENVELOPED_ALGORITHM
        )

        transform_c14n = etree.SubElement(

            transforms,

            etree.QName(
                NAMESPACE_DS,
                "Transform"
            )
        )

        transform_c14n.set(

            "Algorithm",

            C14N_ALGORITHM
        )

        # ====================================================
        # DigestMethod
        # ====================================================

        digest_method = etree.SubElement(

            reference,

            etree.QName(
                NAMESPACE_DS,
                "DigestMethod"
            )
        )

        digest_method.set(

            "Algorithm",

            DIGEST_ALGORITHM
        )

        # ====================================================
        # DigestValue
        # ====================================================

        digest_value_element = etree.SubElement(

            reference,

            etree.QName(
                NAMESPACE_DS,
                "DigestValue"
            )
        )

        digest_value_element.text = (
            digest_value
        )

        log(
            "Estrutura SignedInfo criada"
        )

        # ====================================================
        # 9. CANONICALIZA SignedInfo
        # ====================================================

        log(
            "ETAPA 9: Canonicalizando SignedInfo"
        )

        signed_info_c14n = canonicalizar(
            signed_info
        )

        log(
            f"SignedInfo canonicalizado | "
            f"{len(signed_info_c14n)} bytes"
        )

        # ====================================================
        # 10. ASSINA SignedInfo COM RSA-SHA1
        # ====================================================

        log(
            "ETAPA 10: Assinando SignedInfo "
            "com RSA-SHA1"
        )

        assinatura_binaria = private_key.sign(

            signed_info_c14n,

            padding.PKCS1v15(),

            hashes.SHA1()
        )

        signature_value = base64.b64encode(

            assinatura_binaria

        ).decode("ascii")

        log(
            "Assinatura RSA-SHA1 gerada"
        )

        # ====================================================
        # SignatureValue
        # ====================================================

        signature_value_element = etree.SubElement(

            signature,

            etree.QName(
                NAMESPACE_DS,
                "SignatureValue"
            )
        )

        signature_value_element.text = (
            signature_value
        )

        # ====================================================
        # 11. CERTIFICADO X509
        # ====================================================

        log(
            "ETAPA 11: Inserindo certificado X509"
        )

        key_info = etree.SubElement(

            signature,

            etree.QName(
                NAMESPACE_DS,
                "KeyInfo"
            )
        )

        x509_data = etree.SubElement(

            key_info,

            etree.QName(
                NAMESPACE_DS,
                "X509Data"
            )
        )

        x509_certificate = etree.SubElement(

            x509_data,

            etree.QName(
                NAMESPACE_DS,
                "X509Certificate"
            )
        )

        cert_der = certificate.public_bytes(
            Encoding.DER
        )

        cert_base64 = base64.b64encode(
            cert_der
        ).decode("ascii")

        x509_certificate.text = (
            cert_base64
        )

        log(
            "Certificado X509 inserido"
        )

        # ====================================================
        # 12. INSERE SIGNATURE NA NFe
        # ====================================================

        log(
            "ETAPA 12: Inserindo Signature "
            "depois do infNFe"
        )

        parent = infNFe.getparent()

        if parent is None:

            raise Exception(
                "Elemento pai de infNFe "
                "não encontrado"
            )

        indice_infNFe = parent.index(
            infNFe
        )

        parent.insert(

            indice_infNFe + 1,

            signature
        )

        # ====================================================
        # 13. CONFERE ESTRUTURA
        # ====================================================

        log(
            "ETAPA 13: Conferindo estrutura final"
        )

        filhos_nfe = []

        for filho in parent:

            filhos_nfe.append(
                etree.QName(
                    filho
                ).localname
            )

        log(
            f"Filhos da NFe: "
            f"{filhos_nfe}"
        )

        if "infNFe" not in filhos_nfe:

            raise Exception(
                "infNFe não encontrado "
                "na estrutura final"
            )

        if "Signature" not in filhos_nfe:

            raise Exception(
                "Signature não encontrada "
                "na estrutura final"
            )

        # ====================================================
        # 14. CONFERE ALGORITMOS
        # ====================================================

        log(
            "ETAPA 14: Conferindo algoritmos"
        )

        log(
            f"SignatureMethod: "
            f"{SIGNATURE_ALGORITHM}"
        )

        log(
            f"DigestMethod: "
            f"{DIGEST_ALGORITHM}"
        )

        log(
            f"Canonicalization: "
            f"{C14N_ALGORITHM}"
        )

        # ====================================================
        # 15. GERA XML FINAL
        # ====================================================

        log(
            "ETAPA 15: Gerando XML final"
        )

        xml_final = etree.tostring(

            xml,

            encoding="utf-8",

            xml_declaration=True,

            pretty_print=False
        )

        # ====================================================
        # 16. VALIDA SINTAXE
        # ====================================================

        log(
            "ETAPA 16: Validando sintaxe XML"
        )

        etree.fromstring(
            xml_final
        )

        log(
            "XML final possui sintaxe válida"
        )

        # ====================================================
        # DEBUG
        # ====================================================

        print("\n")

        print("=" * 100)

        print(
            "=============== XML NFC-e "
            "ASSINADO ==============="
        )

        print("=" * 100)

        print(
            xml_final.decode(
                "utf-8"
            )
        )

        print("=" * 100)

        print(
            "=============== FIM XML NFC-e "
            "ASSINADO ==============="
        )

        print("=" * 100)

        print("\n")

        log(
            "===== FIM ASSINATURA XML ====="
        )

        return xml_final

    except Exception as e:

        print("\n")

        print("!" * 100)

        print(
            "=============== ERRO NA "
            "ASSINATURA NFC-e ==============="
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
            "===== ERRO ASSINATURA XML ====="
        )

        log(
            str(e)
        )

        raise