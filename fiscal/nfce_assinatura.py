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
# CANONICALIZA
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
    Assinatura XMLDSig da NFC-e.

    Estrutura:

    NFe
        infNFe
        Signature

    Algoritmos:

    Canonicalização: C14N 1.0
    Digest: SHA1
    Assinatura: RSA-SHA1
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
            f"Certificado carregado | "
            f"{len(pfx_data)} bytes"
        )

        # ====================================================
        # 2. ABRE PFX
        # ====================================================

        log("ETAPA 2: Abrindo PFX")

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
                "Chave privada não encontrada"
            )

        if certificate is None:

            raise Exception(
                "Certificado não encontrado"
            )

        log("Chave privada encontrada")

        log("Certificado encontrado")
        # ====================================================
        # DEBUG DO CERTIFICADO
        # ====================================================

        log("===== DEBUG CERTIFICADO =====")

        subject = certificate.subject.rfc4514_string()
        issuer = certificate.issuer.rfc4514_string()

        log(f"SUBJECT: {subject}")
        log(f"ISSUER: {issuer}")
        log(f"SERIAL: {certificate.serial_number}")
        log(f"VERSÃO: {certificate.version}")

        log(
            f"VALIDADE INÍCIO: "
            f"{certificate.not_valid_before}"
        )

        log(
            f"VALIDADE FIM: "
            f"{certificate.not_valid_after}"
        )

        try:

            basic_constraints = (
                certificate.extensions
                .get_extension_for_class(
                    __import__(
                        "cryptography.x509",
                        fromlist=["BasicConstraints"]
                    ).BasicConstraints
                )
                .value
            )

            log(
                f"BASIC CONSTRAINTS CA: "
                f"{basic_constraints.ca}"
            )

        except Exception as e:

            log(
                f"BASIC CONSTRAINTS: "
                f"não encontrado | {e}"
            )

        try:

            from cryptography import x509

            key_usage = (
                certificate.extensions
                .get_extension_for_class(
                    x509.KeyUsage
                )
                .value
            )

            log(
                f"KEY USAGE "
                f"digital_signature="
                f"{key_usage.digital_signature}"
            )

            log(
                f"KEY USAGE "
                f"key_encipherment="
                f"{key_usage.key_encipherment}"
            )

            log(
                f"KEY USAGE "
                f"key_cert_sign="
                f"{key_usage.key_cert_sign}"
            )

        except Exception as e:

            log(
                f"KEY USAGE: "
                f"não encontrado | {e}"
            )

        try:

            from cryptography import x509

            extended_key_usage = (
                certificate.extensions
                .get_extension_for_class(
                    x509.ExtendedKeyUsage
                )
                .value
            )

            log(
                "EXTENDED KEY USAGE: "
                + ", ".join(
                    oid.dotted_string
                    for oid in extended_key_usage
                )
            )

        except Exception as e:

            log(
                f"EXTENDED KEY USAGE: "
                f"não encontrado | {e}"
            )

        log(
            f"CERTIFICADOS ADICIONAIS NO PFX: "
            f"{len(additional_certificates or [])}"
        )

        log("===== FIM DEBUG CERTIFICADO =====")

        # ====================================================
        # 3. PARSE XML
        # ====================================================

        log("ETAPA 3: Fazendo parse do XML")

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
            f"Raiz XML: {xml.tag}"
        )

        # ====================================================
        # 4. LOCALIZA infNFe
        # ====================================================

        log("ETAPA 4: Localizando infNFe")

        infNFe = xml.find(
            f".//{{{NAMESPACE_NFE}}}infNFe"
        )

        if infNFe is None:

            raise Exception(
                "infNFe não encontrado"
            )

        infNFe_id = infNFe.get("Id")

        if not infNFe_id:

            raise Exception(
                "Id do infNFe não encontrado"
            )

        if not infNFe_id.startswith("NFe"):

            raise Exception(
                f"Id do infNFe inválido: "
                f"{infNFe_id}"
            )

        log(
            f"Id encontrado: {infNFe_id}"
        )

        # ====================================================
        # 5. VERIFICA ASSINATURA EXISTENTE
        # ====================================================

        assinatura_existente = xml.find(
            f".//{{{NAMESPACE_DS}}}Signature"
        )

        if assinatura_existente is not None:

            raise Exception(
                "XML já possui Signature"
            )

        # ====================================================
        # 6. CRIA SIGNATURE
        # ====================================================

        log(
            "ETAPA 6: Criando Signature"
        )

        signature = etree.Element(

            etree.QName(
                NAMESPACE_DS,
                "Signature"
            ),

            nsmap={
                "ds": NAMESPACE_DS
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
        # DigestValue vazio por enquanto
        # ====================================================

        digest_value_element = etree.SubElement(

            reference,

            etree.QName(
                NAMESPACE_DS,
                "DigestValue"
            )
        )

        # ====================================================
        # SignatureValue vazio por enquanto
        # ====================================================

        signature_value_element = etree.SubElement(

            signature,

            etree.QName(
                NAMESPACE_DS,
                "SignatureValue"
            )
        )

        # ====================================================
        # KeyInfo
        # ====================================================

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

        x509_certificate.text = cert_base64

        # ====================================================
        # 7. INSERE SIGNATURE NA ÁRVORE PRIMEIRO
        # ====================================================

        log(
            "ETAPA 7: Inserindo Signature "
            "na estrutura final"
        )

        parent = infNFe.getparent()

        if parent is None:

            raise Exception(
                "Elemento NFe não encontrado"
            )

        indice_infNFe = parent.index(
            infNFe
        )

        parent.insert(
            indice_infNFe + 1,
            signature
        )

        log(
            "Signature inserida depois do infNFe"
        )

        # ====================================================
        # 8. CALCULA DIGEST DO infNFe
        # ====================================================

        log(
            "ETAPA 8: Canonicalizando infNFe"
        )

        infNFe_c14n = canonicalizar(
            infNFe
        )

        log(
            f"infNFe C14N: "
            f"{len(infNFe_c14n)} bytes"
        )

        digest = hashlib.sha1(
            infNFe_c14n
        ).digest()

        digest_value = base64.b64encode(
            digest
        ).decode("ascii")

        digest_value_element.text = (
            digest_value
        )

        log(
            f"DigestValue: {digest_value}"
        )

        # ====================================================
        # 9. CANONICALIZA SignedInfo JÁ NA ÁRVORE
        # ====================================================

        log(
            "ETAPA 9: Canonicalizando SignedInfo "
            "no contexto final"
        )

        signed_info_c14n = canonicalizar(
            signed_info
        )

        log(
            f"SignedInfo C14N: "
            f"{len(signed_info_c14n)} bytes"
        )

        # ====================================================
        # 10. RSA-SHA1
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

        signature_value_element.text = (
            signature_value
        )

        log(
            "SignatureValue calculado"
        )

        # ====================================================
        # 11. VERIFICAÇÃO LOCAL DA ASSINATURA
        # ====================================================

        log(
            "ETAPA 11: Verificando assinatura "
            "localmente"
        )

        certificate.public_key().verify(

            assinatura_binaria,

            signed_info_c14n,

            padding.PKCS1v15(),

            hashes.SHA1()
        )

        log(
            "Assinatura RSA validada localmente"
        )

        # ====================================================
        # 12. RECALCULA DIGEST PARA CONFERÊNCIA
        # ====================================================

        log(
            "ETAPA 12: Conferindo DigestValue"
        )

        infNFe_c14n_check = canonicalizar(
            infNFe
        )

        digest_check = base64.b64encode(

            hashlib.sha1(
                infNFe_c14n_check
            ).digest()

        ).decode("ascii")

        if digest_check != digest_value:

            raise Exception(
                "DigestValue mudou após "
                "montagem da assinatura"
            )

        log(
            "DigestValue permanece válido"
        )

        # ====================================================
        # 13. CONFERE ESTRUTURA
        # ====================================================

        filhos = [

            etree.QName(
                filho
            ).localname

            for filho in parent
        ]

        log(
            f"Filhos da NFe: {filhos}"
        )

        if filhos[0] != "infNFe":

            raise Exception(
                "infNFe não é o primeiro "
                "elemento da NFe"
            )

        if len(filhos) < 2:

            raise Exception(
                "Signature não encontrada "
                "depois do infNFe"
            )

        if filhos[1] != "Signature":

            raise Exception(
                "Signature não está imediatamente "
                "depois do infNFe"
            )

        # ====================================================
        # 14. XML FINAL
        # ====================================================

        log(
            "ETAPA 14: Gerando XML final"
        )

        xml_final = etree.tostring(

            xml,

            encoding="utf-8",

            xml_declaration=True,

            pretty_print=False
        )

        # ====================================================
        # 15. REPARSE E CONFERE DIGEST
        # ====================================================

        log(
            "ETAPA 15: Reabrindo XML final "
            "para conferir estabilidade"
        )

        xml_check = etree.fromstring(
            xml_final
        )

        infNFe_check = xml_check.find(
            f".//{{{NAMESPACE_NFE}}}infNFe"
        )

        if infNFe_check is None:

            raise Exception(
                "infNFe desapareceu do XML final"
            )

        digest_final = base64.b64encode(

            hashlib.sha1(

                canonicalizar(
                    infNFe_check
                )

            ).digest()

        ).decode("ascii")

        if digest_final != digest_value:

            print(
                f"DIGEST ORIGINAL: {digest_value}"
            )

            print(
                f"DIGEST APÓS SERIALIZAÇÃO: "
                f"{digest_final}"
            )

            raise Exception(
                "DigestValue alterado após "
                "serialização do XML"
            )

        log(
            "Digest permanece igual "
            "após serialização"
        )

        # ====================================================
        # 16. DEBUG FINAL
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
            f"DIGEST FINAL: {digest_value}"
        )

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