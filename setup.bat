@echo off
echo ==========================================
echo   INSTALADOR DO PROJETO GED_PROFISSIONAL
echo ==========================================

REM 1) Criar ambiente virtual
echo Criando ambiente virtual .venv_ged ...
python -m venv .venv_ged

REM 2) Ativar ambiente virtual
echo Ativando ambiente virtual...
call .venv_ged\Scripts\activate

REM 3) Atualizar pip
echo Atualizando pip...
python -m pip install --upgrade pip

REM 4) Instalar dependências
echo Instalando dependencias do requirements.txt...
pip install -r requirements.txt

REM 5) Aplicar migrações
echo Aplicando migracoes do banco de dados...
python manage.py migrate

REM 6) Coletar arquivos estáticos
echo Coletando arquivos estaticos...
python manage.py collectstatic --noinput

REM 7) Rodar o servidor
echo Iniciando servidor...
python manage.py runserver

pause
