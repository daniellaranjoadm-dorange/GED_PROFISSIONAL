import os
import subprocess
import sys

# Caminho do projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("===========================================")
print("   INSTALADOR DO PROJETO GED_PROFISSIONAL")
print("===========================================\n")


# --------------------------------------------------------
#  1) Criar ambiente virtual .venv_ged
# --------------------------------------------------------
VENV_PATH = os.path.join(BASE_DIR, ".venv_ged")

if not os.path.exists(VENV_PATH):
    print("Criando ambiente virtual .venv_ged ...")
    subprocess.run([sys.executable, "-m", "venv", VENV_PATH])
else:
    print("Ambiente virtual .venv_ged já existe. Pulando etapa.")


# --------------------------------------------------------
# 2) Ativar ambiente virtual (Windows PowerShell)
# --------------------------------------------------------
ACTIVATE = os.path.join(VENV_PATH, "Scripts", "activate")

print("Ativando ambiente virtual...")
os.system(f'"{ACTIVATE}"')


# --------------------------------------------------------
# 3) Atualizar pip
# --------------------------------------------------------
print("Atualizando pip...")
subprocess.run([os.path.join(VENV_PATH, "Scripts", "python.exe"), "-m", "pip", "install", "--upgrade", "pip"])


# --------------------------------------------------------
# 4) Instalar dependências
# --------------------------------------------------------
REQ = os.path.join(BASE_DIR, "requirements.txt")

if os.path.exists(REQ):
    print("Instalando dependencias do requirements.txt...")
    subprocess.run([os.path.join(VENV_PATH, "Scripts", "python.exe"), "-m", "pip", "install", "-r", REQ])
else:
    print("⚠ ATENÇÃO: requirements.txt não encontrado!")


# --------------------------------------------------------
# 5) Apli
