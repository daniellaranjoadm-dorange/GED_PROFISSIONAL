from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.conf import settings
import logging

from .models import UserConfig, SolicitacaoAcesso
from .forms import UserConfigForm, SolicitacaoAcessoForm
from .permissions import has_perm

logger = logging.getLogger(__name__)


# ==========================================================================
# 🏁 LANDING PAGE INSTITUCIONAL (página inicial pública)
# ==========================================================================
def landing(request):
    return render(request, "contas/landing.html")


# ==========================================================================
# 🔐 LOGIN (versão reforçada)
# ==========================================================================
def login_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        try:
            user = authenticate(request, username=username, password=password)
        except Exception as exc:
            logger.exception("Erro no authenticate() dentro do login_view")

            messages.error(
                request,
                "Erro interno ao validar suas credenciais. Tente novamente em instantes."
            )
            return render(request, "contas/login.html")

        if user:
            login(request, user)
            next_url = request.GET.get("next") or "documentos:listar_documentos"
            return redirect(next_url)

        messages.error(request, "Usuário ou senha incorretos!")

    return render(request, "contas/login.html")


# ==========================================================================
# 🚪 LOGOUT
# ==========================================================================
def logout_view(request):
    logout(request)
    return redirect("contas:login")


# ==========================================================================
# 🧩 MINHAS CONFIGURAÇÕES
# ==========================================================================
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


# ==========================================================================
# 📨 SOLICITAÇÃO DE ACESSO (PÚBLICA) — agora integrado com landing
# ==========================================================================
def solicitar_acesso(request):
    if request.method == "POST":
        form = SolicitacaoAcessoForm(request.POST)
        if form.is_valid():
            lead = form.save()

            # envio opcional de e-mail para o administrador
            try:
                send_mail(
                    subject="📥 Nova solicitação de acesso ao GED D'OR@NGE",
                    message=f"""
Nova solicitação recebida:

Nome: {lead.nome}
Empresa/Projeto: {lead.empresa}
E-mail: {lead.email}
Telefone/Whats: {lead.telefone}
Cargo: {lead.cargo}

Mensagem informada:
{lead.mensagem}
""",
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[getattr(settings, "GED_CONTATO_EMAIL", "seuemail@empresa.com")],
                    fail_silently=True,
                )
            except:
                pass

            messages.success(request, "Sua solicitação foi enviada com sucesso! Retornaremos em breve.")
            return redirect("contas:landing")

    else:
        form = SolicitacaoAcessoForm()

    return render(request, "contas/solicitar_acesso.html", {"form": form})


# ==========================================================================
# 🛡 PERMISSÃO: Master Admin
# ==========================================================================
def is_master(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "is_master", False))


# ==========================================================================
# 🗂 PAINEL INTERNO DE SOLICITAÇÕES
# ==========================================================================
@login_required
@user_passes_test(is_master)
def painel_solicitacoes(request):
    solicitacoes = SolicitacaoAcesso.objects.order_by("-data")
    return render(request, "contas/painel_solicitacoes.html", {"solicitacoes": solicitacoes})


# ==========================================================================
# ✔ APROVAR SOLICITAÇÃO
# ==========================================================================
@login_required
@user_passes_test(is_master)
def aprovar_solicitacao(request, id):
    sol = get_object_or_404(SolicitacaoAcesso, id=id)
    sol.status = "aprovado"
    sol.save()
    messages.success(request, f"Solicitação de {sol.nome} foi APROVADA.")
    return redirect("contas:painel_solicitacoes")


# ==========================================================================
# ✖ NEGAR SOLICITAÇÃO
# ==========================================================================
@login_required
@user_passes_test(is_master)
def negar_solicitacao(request, id):
    sol = get_object_or_404(SolicitacaoAcesso, id=id)
    sol.status = "negado"
    sol.save()
    messages.error(request, f"Solicitação de {sol.nome} foi NEGADA.")
    return redirect("contas:painel_solicitacoes")
