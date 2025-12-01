from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import UserConfig, SolicitacaoAcesso
from .forms import UserConfigForm, SolicitacaoAcessoForm


# =====================================================================
# 🔐 LOGIN
# =====================================================================
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("documentos:listar_documentos")
        else:
            messages.error(request, "Usuário ou senha incorretos!")

    return render(request, "contas/login.html")


# =====================================================================
# 🚪 LOGOUT
# =====================================================================
def logout_view(request):
    logout(request)
    return redirect("contas:login")


# =====================================================================
# ⚙ MINHAS CONFIGURAÇÕES
# =====================================================================
@login_required
def minhas_configuracoes(request):
    config, _ = UserConfig.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações atualizadas com sucesso!")
            return redirect("contas:minhas_configuracoes")
    else:
        form = UserConfigForm(instance=config)

    return render(request, "contas/minhas_configuracoes.html", {"form": form})


# =====================================================================
# 📨 FORMULÁRIO PÚBLICO DE SOLICITAÇÃO
# =====================================================================
def solicitar_acesso(request):
    form = SolicitacaoAcessoForm()

    if request.method == "POST":
        form = SolicitacaoAcessoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Sua solicitação foi enviada com sucesso!")
            return redirect("contas:login")

    return render(request, "contas/solicitar_acesso.html", {"form": form})


# =====================================================================
# 🔐 PERMISSÃO: somente superuser ou MASTER
# =====================================================================
def is_master(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "is_master", False))


# =====================================================================
# 📌 PAINEL INTERNO DE SOLICITAÇÕES
# =====================================================================
@login_required
@user_passes_test(is_master)
def painel_solicitacoes(request):
    solicitacoes = SolicitacaoAcesso.objects.order_by("-data")
    return render(request, "contas/painel_solicitacoes.html", {
        "solicitacoes": solicitacoes
    })


# =====================================================================
# ✔ APROVAR SOLICITAÇÃO
# =====================================================================
@login_required
@user_passes_test(is_master)
def aprovar_solicitacao(request, id):
    sol = get_object_or_404(SolicitacaoAcesso, id=id)
    sol.status = "aprovado"
    sol.save()
    messages.success(request, f"Solicitação de {sol.nome} foi APROVADA.")
    return redirect("contas:painel_solicitacoes")


# =====================================================================
# ✖ NEGAR SOLICITAÇÃO
# =====================================================================
@login_required
@user_passes_test(is_master)
def negar_solicitacao(request, id):
    sol = get_object_or_404(SolicitacaoAcesso, id=id)
    sol.status = "negado"
    sol.save()
    messages.error(request, f"Solicitação de {sol.nome} foi NEGADA.")
    return redirect("contas:painel_solicitacoes")
