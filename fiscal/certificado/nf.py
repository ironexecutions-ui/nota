import os
import tempfile
import requests
import urllib3

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)


# ============================================================
# DESATIVA AVISO APENAS PARA ESTE TESTE
# ============================================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
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
    "ws/NFeStatusServico4.asmx"
)


# ============================================================
# SOAP STATUS SERVIÇO
# ============================================================

SOAP_XML = """<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">

    <soap12:Header>

        <nfeCabecMsg
            xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">

            <cUF>35</cUF>
            <versaoDados>4.00</versaoDados>

        </nfeCabecMsg>

    </soap12:Header>

    <soap12:Body>

        <nfeDadosMsg
            xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">

            <consStatServ
                xmlns="http://www.portalfiscal.inf.br/nfe"
                versao="4.00">

                <tpAmb>2</tpAmb>
                <cUF>35</cUF>
                <xServ>STATUS</xServ>

            </consStatServ>

        </nfeDadosMsg>

    </soap12:Body>

</soap12:Envelope>
"""


def main():

    print()
    print("=" * 100)
    print("TESTE CERTIFICADO PFX COM SEFAZ-SP")
    print("=" * 100)

    cert_path = None
    key_path = None

    try:

        # ====================================================
        # 1. VERIFICAR PFX
        # ====================================================

        print()
        print("[1] Verificando arquivo PFX")
        print(f"Caminho: {PFX_PATH}")

        if not os.path.exists(PFX_PATH):
            raise Exception(
                f"PFX não encontrado: {PFX_PATH}"
            )

        tamanho = os.path.getsize(PFX_PATH)

        print(
            f"Tamanho: {tamanho} bytes"
        )

        # ====================================================
        # 2. ABRIR PFX
        # ====================================================

        print()
        print("[2] Abrindo certificado")

        with open(PFX_PATH, "rb") as f:
            pfx_data = f.read()

        private_key, certificate, additional = (
            pkcs12.load_key_and_certificates(
                pfx_data,
                SENHA_PFX.encode()
            )
        )

        if private_key is None:
            raise Exception(
                "PFX não contém chave privada"
            )

        if certificate is None:
            raise Exception(
                "PFX não contém certificado"
            )

        print("Certificado aberto com sucesso")

        print()
        print("SUBJECT:")
        print(
            certificate.subject.rfc4514_string()
        )

        print()
        print("ISSUER:")
        print(
            certificate.issuer.rfc4514_string()
        )

        print()
        print("SERIAL:")
        print(
            certificate.serial_number
        )

        print()
        print("VALIDADE INÍCIO:")
        print(
            certificate.not_valid_before_utc
        )

        print()
        print("VALIDADE FIM:")
        print(
            certificate.not_valid_after_utc
        )

        print()
        print(
            "CERTIFICADOS ADICIONAIS:",
            len(additional or [])
        )

        # ====================================================
        # 3. GERAR PEM TEMPORÁRIO
        # ====================================================

        print()
        print("[3] Gerando PEM para conexão TLS")

        cert_pem = certificate.public_bytes(
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

        cert_path = cert_file.name
        key_path = key_file.name

        cert_file.write(cert_pem)
        key_file.write(key_pem)

        cert_file.close()
        key_file.close()

        print("PEM gerado com sucesso")

        print()
        print(f"Cert PEM temporário: {cert_path}")
        print(f"Key PEM temporária: {key_path}")

        # ====================================================
        # 4. TESTAR HTTPS COM CERTIFICADO
        # ====================================================

        print()
        print("[4] Conectando à SEFAZ-SP")
        print(URL_SEFAZ)

        print()
        print(
            "ATENÇÃO: verificação do certificado HTTPS "
            "do servidor está desativada SOMENTE neste teste."
        )

        headers = {
            "Content-Type": (
                "application/soap+xml; "
                "charset=utf-8"
            )
        }

        response = requests.post(
            URL_SEFAZ,
            data=SOAP_XML.encode("utf-8"),
            headers=headers,
            cert=(
                cert_path,
                key_path
            ),
            timeout=30,

            # =================================================
            # SOMENTE PARA DIAGNÓSTICO
            # =================================================
            verify=False
        )

        # ====================================================
        # 5. RESULTADO HTTP
        # ====================================================

        print()
        print("=" * 100)
        print("RESPOSTA SEFAZ")
        print("=" * 100)

        print()
        print(
            f"HTTP STATUS: {response.status_code}"
        )

        print()
        print("CONTENT-TYPE:")
        print(
            response.headers.get("content-type")
        )

        print()
        print("BODY:")
        print(response.text)

        print()
        print("=" * 100)
        print("ANÁLISE AUTOMÁTICA")
        print("=" * 100)

        # ====================================================
        # HTTP 200
        # ====================================================

        if response.status_code == 200:

            print()
            print(
                "[OK] A conexão HTTPS chegou corretamente "
                "ao WebService da SEFAZ."
            )

            # ================================================
            # STATUS 107
            # ================================================

            if "<cStat>107</cStat>" in response.text:

                print()
                print("=" * 100)
                print("RESULTADO EXCELENTE")
                print("=" * 100)

                print()
                print(
                    "A SEFAZ retornou cStat 107."
                )

                print(
                    "Significado: Serviço em Operação."
                )

                print()
                print(
                    "O certificado cliente conseguiu participar "
                    "da conexão TLS com a SEFAZ."
                )

                print()
                print(
                    "Isso indica que o PFX está funcional "
                    "para autenticação HTTPS."
                )

                print()
                print(
                    "Se a emissão continuar retornando 290, "
                    "o próximo diagnóstico deve ficar concentrado "
                    "na assinatura XML da NFC-e."
                )

            # ================================================
            # OUTRO CSTAT
            # ================================================

            elif "<cStat>" in response.text:

                print()
                print(
                    "[ATENÇÃO] A SEFAZ respondeu normalmente, "
                    "mas retornou outro cStat."
                )

                print()
                print(
                    "Precisamos analisar o cStat e xMotivo "
                    "mostrados no BODY acima."
                )

            # ================================================
            # SEM CSTAT
            # ================================================

            else:

                print()
                print(
                    "[ATENÇÃO] HTTP 200 recebido, mas não "
                    "encontrei <cStat> na resposta."
                )

                print()
                print(
                    "Precisamos analisar o BODY completo."
                )

        # ====================================================
        # HTTP DIFERENTE DE 200
        # ====================================================

        else:

            print()
            print(
                "[ERRO] A SEFAZ retornou HTTP diferente de 200."
            )

            print()
            print(
                f"HTTP recebido: {response.status_code}"
            )

            print()
            print(
                "Analise o BODY acima para identificar "
                "a causa."
            )

    # ========================================================
    # ERRO SSL
    # ========================================================

    except requests.exceptions.SSLError as e:

        print()
        print("=" * 100)
        print("ERRO SSL / CERTIFICADO")
        print("=" * 100)

        print()
        print(
            f"TIPO: {type(e).__name__}"
        )

        print()
        print(
            f"MENSAGEM: {str(e)}"
        )

        print()
        print(
            "Mesmo com verify=False ocorreu erro SSL."
        )

        print(
            "Nesse caso precisamos investigar o handshake "
            "TLS e o certificado cliente."
        )

    # ========================================================
    # TIMEOUT
    # ========================================================

    except requests.exceptions.Timeout as e:

        print()
        print("=" * 100)
        print("TIMEOUT")
        print("=" * 100)

        print()
        print(
            f"TIPO: {type(e).__name__}"
        )

        print()
        print(
            f"MENSAGEM: {str(e)}"
        )

    # ========================================================
    # CONNECTION ERROR
    # ========================================================

    except requests.exceptions.ConnectionError as e:

        print()
        print("=" * 100)
        print("ERRO DE CONEXÃO")
        print("=" * 100)

        print()
        print(
            f"TIPO: {type(e).__name__}"
        )

        print()
        print(
            f"MENSAGEM: {str(e)}"
        )

    # ========================================================
    # ERRO GERAL
    # ========================================================

    except Exception as e:

        print()
        print("=" * 100)
        print("ERRO")
        print("=" * 100)

        print()
        print(
            f"TIPO: {type(e).__name__}"
        )

        print()
        print(
            f"MENSAGEM: {str(e)}"
        )

    # ========================================================
    # LIMPEZA
    # ========================================================

    finally:

        print()
        print("[5] Limpando arquivos temporários")

        if cert_path and os.path.exists(cert_path):

            try:
                os.remove(cert_path)
                print(
                    "Certificado PEM temporário removido"
                )
            except Exception as e:
                print(
                    f"Não foi possível remover cert PEM: {e}"
                )

        if key_path and os.path.exists(key_path):

            try:
                os.remove(key_path)
                print(
                    "Chave PEM temporária removida"
                )
            except Exception as e:
                print(
                    f"Não foi possível remover key PEM: {e}"
                )

        print()
        print("=" * 100)
        print("FIM DO TESTE")
        print("=" * 100)


if __name__ == "__main__":
    main()