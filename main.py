from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ==================================================
# IMPORTAÇÃO DOS MÓDULOS FISCAIS
# ==================================================

from fiscal.nfce_service import router as nfce_router
from fiscal.nfe_service import router as nfe_router


app = FastAPI()


# ==================================================
# CORS
# ==================================================

origins = [
    "*",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://ironexecutions.com.br",
    "https://ironexecutions-backend.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ==================================================
# REGISTRO DOS MÓDULOS FISCAIS
# ==================================================

# NFC-e MODELO 65
app.include_router(
    nfce_router,
    prefix="/nfce"
)

# NF-e MODELO 55
app.include_router(
    nfe_router
)


# ==================================================
# ROTAS PRINCIPAIS
# ==================================================

@app.get("/")
def raiz():
    return {
        "status": "API fiscal está funcionando"
    }


@app.get("/teste")
def teste():
    return {
        "mensagem": "Servidor fiscal conectado com sucesso"
    }
