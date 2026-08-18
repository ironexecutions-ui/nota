from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fiscal.nfce_service import router as nfce_router

app = FastAPI()

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

# 🔹 REGISTRA O MÓDULO FISCAL
app.include_router(nfce_router, prefix="/nfce")

@app.get("/")
def raiz():
    return {"status": "API fiscal está funcionando"}

@app.get("/teste")
def teste():
    return {"mensagem": "Servidor fiscal conectado com sucesso"}
