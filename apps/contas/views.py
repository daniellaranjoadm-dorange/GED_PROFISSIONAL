from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.conf import settings
from django.template import TemplateDoesNotExist
from django.http import HttpResponse
import logging

from .models import UserConfig, SolicitacaoAcesso
from .forms import UserConfigForm, SolicitacaoAcessoForm

logger = logging.getLogger(__name__)


def landing(request):
    return render(request, "contas/landing.html")


def login_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        try:
            user = authenticate(request, username=username, password=password)
        except Exception:
            logger.exception("Erro no authenticate() dentro do login_view")
            messages.error(request, "Erro interno ao validar suas credenciais. Tente novamente.")
            return render(request, "contas/login.html")

        if user:
            login(request, user)
            next_url = request.GET.get("next") or "documentos:listar_documentos"
            return redirect(next_url)

        messages.error(request, "Usuário ou senha incorretos!")

    return render(request, "contas/login.html")


def logout_view(request):
    logout(request)
    return redirect("contas:login")


@login_required
def minhas_configuracoes(request):
    """
    Evita 500 mesmo se:
    - template estiver faltando
    - form/model tiverem alguma inconsistência
    """
    try:
        config, _ = UserConfig.objects.get_or_create(user=request.user)
    except Exception:
        logger.exception("Falha ao carregar/criar UserConfig")
        return HttpResponse("Erro ao carregar configurações do usuário. Verifique logs.", status=500)

    try:
        if request.method == "POST":
            form = UserConfigForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
                messages.success(request, "Configurações atualizadas com sucesso!")
                return redirect("contas:minhas_configuracoes")
        else:
            form = UserConfigForm(instance=config)
    except Exception:
        logger.exception("Falha ao processar UserConfigForm")
        return HttpResponse("Erro ao processar formulário de configurações. Verifique logs.", status=500)

    # Render normal; se template não existir, cai num HTML mínimo (não quebra)
    try:
        return render(request, "contas/minhas_configuracoes.html", {"form": form})
    except TemplateDoesNotExist:
        html = f"""
        <h2>Minhas configurações</h2>
        <p><b>Template contas/minhas_configuracoes.html não encontrado.</b></p>
        <form method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value="">
            {form.as_p()}
            <button type="submit">Salvar</button>
        </form>
        """
        return HttpResponse(html)


def solicitar_acesso(request):
    if request.method == "POST":
        form = SolicitacaoAcessoForm(request.POST)
        if form.is_valid():
            lead = form.save()

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
            except Exception:
                pass

            messages.success(request, "Sua solicitação foi enviada com sucesso! Retornaremos em breve.")
            return redirect("contas:landing")
    else:
        form = SolicitacaoAcessoForm()

    return render(request, "contas/solicitar_acesso.html", {"form": form})


def is_master(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "is_master", False))


@login_required
@user_passes_test(is_master)
def painel_solicitacoes(request):
    solicitacoes = SolicitacaoAcesso.objects.order_by("-data")
    return render(request, "contas/painel_solicitacoes.html", {"solicitacoes": solicitacoes})


@login_required
@user_passes_test(is_master)
def aprovar_solicitacao(request, id):
    sol = get_object_or_404(SolicitacaoAcesso, id=id)
    sol.status = "aprovado"
    sol.save()
    messages.success(request, f"Solicitação de {sol.nome} foi APROVADA.")
    return redirect("contas:painel_solicitacoes")


@login_required
@user_passes_test(is_master)
def negar_solicitacao(request, id):
    sol = get_object_or_404(SolicitacaoAcesso, id=id)
    sol.status = "negado"
    sol.save()
    messages.error(request, f"Solicitação de {sol.nome} foi NEGADA.")
    return redirect("contas:painel_solicitacoes")


@login_required
@user_passes_test(is_master)
def usuarios_permissoes(request):
    """
    Por padrão, manda para o Admin do Django (não quebra e é completo).
    Depois fazemos UI própria (tabela de usuários, grupos e permissões).
    """
    return redirect("/admin/auth/user/")
