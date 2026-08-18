from datetime import datetime

from signxml import XMLSigner, methods

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding
)

from cryptography.hazmat.backends import default_backend

from lxml import etree


NAMESPACE_NFE = "http://www.portalfiscal.inf.br/nfe"
NAMESPACE_DS = "http://www.w3.org/2000/09/xmldsig#"


def log(msg):
    print(
        f"[NFCe-ASSINATURA]"
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        f"{msg}"
    )


def assinar_xml(
    xml_bytes,
    certificado_path,
    senha
):
    """
    Assina XML NFC-e no padrão XMLDSig utilizado pela NF-e/NFC-e.
    """

    log("===== INÍCIO ASSINATURA XML =====")

    try:

        # ==========================================
        # 1. CERTIFICADO
        # ==========================================
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

        # ==========================================
        # 2. CARREGA PFX
        # ==========================================
        log("ETAPA 2: Abrindo certificado PFX")

        private_key, certificate, additional_certificates = (
            pkcs12.load_key_and_certificates(
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
                "Certificado não encontrado no arquivo PFX"
            )

        log("Chave privada encontrada")
        log("Certificado encontrado")

        if additional_certificates:
            log(
                f"Certificados adicionais encontrados: "
                f"{len(additional_certificates)}"
            )
        else:
            log("Nenhum certificado adicional será enviado")

        # ==========================================
        # 3. CERTIFICADO PEM
        # ==========================================
        log("ETAPA 3: Convertendo certificado para PEM")

        cert_pem = certificate.public_bytes(
            Encoding.PEM
        )

        log("Certificado convertido para PEM")

        # ==========================================
        # 4. PARSE XML
        # ==========================================
        log("ETAPA 4: Fazendo parse do XML")

        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode("utf-8")

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

        # ==========================================
        # 5. LOCALIZA infNFe
        # ==========================================
        log("ETAPA 5: Procurando infNFe")

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
                "Atributo Id do <infNFe> não encontrado"
            )

        if not infNFe_id.startswith("NFe"):
            raise Exception(
                f"Id do infNFe inválido: {infNFe_id}"
            )

        log(
            f"infNFe encontrado com Id: "
            f"{infNFe_id}"
        )

        # ==========================================
        # 6. VERIFICA ASSINATURA EXISTENTE
        # ==========================================
        log(
            "ETAPA 6: Verificando se XML "
            "já possui assinatura"
        )

        assinatura_existente = xml.find(
            f".//{{{NAMESPACE_DS}}}Signature"
        )

        if assinatura_existente is not None:
            raise Exception(
                "XML já possui assinatura digital"
            )

        log("XML ainda não possui assinatura")

        # ==========================================
        # 7. CONFIGURA ASSINATURA
        # ==========================================
        log("ETAPA 7: Configurando XMLDSig")

        log("SignatureMethod: RSA-SHA1")
        log("DigestMethod: SHA1")
        log("Canonicalization: C14N 1.0")
        log("Método: Enveloped")

        signer = XMLSigner(
            method=methods.enveloped,

            signature_algorithm="rsa-sha1",

            digest_algorithm="sha1",

            c14n_algorithm=(
                "http://www.w3.org/TR/"
                "2001/REC-xml-c14n-20010315"
            )
        )

        # ==========================================
        # 8. ASSINA infNFe
        # ==========================================
        log("ETAPA 8: Assinando infNFe")

        signed_infNFe = signer.sign(
            infNFe,
            key=private_key,
            cert=cert_pem,
            reference_uri=f"#{infNFe_id}"
        )

        log("Assinatura criptográfica gerada")

        # ==========================================
        # 9. LOCALIZA SIGNATURE
        # ==========================================
        log("ETAPA 9: Localizando Signature")

        signature = signed_infNFe.find(
            f".//{{{NAMESPACE_DS}}}Signature"
        )

        if signature is None:
            raise Exception(
                "Signature não encontrada "
                "após assinatura"
            )

        log("Signature encontrada")

        # ==========================================
        # 10. REMOVE SIGNATURE DO infNFe
        # ==========================================
        log(
            "ETAPA 10: Removendo Signature "
            "de dentro do infNFe"
        )

        signature_parent = signature.getparent()

        if signature_parent is None:
            raise Exception(
                "Não foi possível localizar "
                "o pai da Signature"
            )

        signature_parent.remove(
            signature
        )

        log(
            "Signature removida temporariamente "
            "do infNFe"
        )

        # ==========================================
        # 11. SUBSTITUI infNFe
        # ==========================================
        log(
            "ETAPA 11: Substituindo infNFe "
            "original pelo assinado"
        )

        parent = infNFe.getparent()

        if parent is None:
            raise Exception(
                "Elemento pai do infNFe "
                "não encontrado"
            )

        parent.replace(
            infNFe,
            signed_infNFe
        )

        log("infNFe substituído")

        # ==========================================
        # 12. SIGNATURE DEPOIS DO infNFe
        # ==========================================
        log(
            "ETAPA 12: Inserindo Signature "
            "como filha de NFe"
        )

        signed_inf_index = parent.index(
            signed_infNFe
        )

        parent.insert(
            signed_inf_index + 1,
            signature
        )

        log(
            "Signature posicionada imediatamente "
            "depois do infNFe"
        )

        # ==========================================
        # 13. VALIDA POSIÇÃO
        # ==========================================
        log(
            "ETAPA 13: Validando estrutura "
            "final da NFe"
        )

        filhos_nfe = []

        for filho in parent:
            filhos_nfe.append(
                etree.QName(filho).localname
            )

        log(
            f"Filhos de NFe: {filhos_nfe}"
        )

        if "infNFe" not in filhos_nfe:
            raise Exception(
                "infNFe desapareceu da estrutura"
            )

        if "Signature" not in filhos_nfe:
            raise Exception(
                "Signature não está dentro de NFe"
            )

        # ==========================================
        # 14. VALIDA ALGORITMOS GERADOS
        # ==========================================
        log(
            "ETAPA 14: Conferindo algoritmos "
            "da assinatura"
        )

        signature_method = signature.find(
            f".//{{{NAMESPACE_DS}}}SignatureMethod"
        )

        digest_method = signature.find(
            f".//{{{NAMESPACE_DS}}}DigestMethod"
        )

        if signature_method is None:
            raise Exception(
                "SignatureMethod não encontrado"
            )

        if digest_method is None:
            raise Exception(
                "DigestMethod não encontrado"
            )

        signature_algorithm = (
            signature_method.get("Algorithm")
        )

        digest_algorithm = (
            digest_method.get("Algorithm")
        )

        log(
            f"SignatureMethod final: "
            f"{signature_algorithm}"
        )

        log(
            f"DigestMethod final: "
            f"{digest_algorithm}"
        )

        # ==========================================
        # 15. XML FINAL
        # ==========================================
        log("ETAPA 15: Gerando XML final")

        xml_final = etree.tostring(
            xml,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False
        )

        # ==========================================
        # 16. VALIDA SINTAXE
        # ==========================================
        log(
            "ETAPA 16: Validando sintaxe "
            "do XML final"
        )

        etree.fromstring(
            xml_final
        )

        log("XML final possui sintaxe válida")

        # ==========================================
        # DEBUG
        # ==========================================
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

        log("===== FIM ASSINATURA XML =====")

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

        log("===== ERRO ASSINATURA XML =====")
        log(str(e))

        raise