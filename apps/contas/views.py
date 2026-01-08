from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template import TemplateDoesNotExist
from django.http import HttpResponse
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme
import logging

from .models import UserConfig
from .forms import UserConfigForm

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
            messages.error(request, "Erro interno ao validar suas credenciais.")
            return render(request, "contas/login.html")

        if user:
            login(request, user)

            # next seguro (evita open-redirect)
            next_url = (
                request.POST.get("next")
                or request.GET.get("next")
                or reverse("documentos:listar_documentos")
            )

            if not url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                next_url = reverse("documentos:listar_documentos")

            return redirect(next_url)

        messages.error(request, "Usuário ou senha incorretos!")

    return render(request, "contas/login.html")


def logout_view(request):
    logout(request)
    return redirect("contas:login")


@login_required
def minhas_configuracoes(request):
    try:
        config, _ = UserConfig.objects.get_or_create(user=request.user)
    except Exception:
        logger.exception("Falha ao carregar/criar UserConfig")
        return HttpResponse("Erro ao carregar configurações do usuário.", status=500)

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
        return HttpResponse("Erro ao processar formulário.", status=500)

    try:
        return render(request, "contas/minhas_configuracoes.html", {"form": form})
    except TemplateDoesNotExist:
        # fallback simples (não quebra)
        return HttpResponse(form.as_p())


def is_master(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "is_master", False))


# ✅ Compatibilidade:
# tudo que for "Solicitação de Acesso" fica no app solicitacoes.
# aqui no contas a gente só redireciona (compatibilidade com links antigos)
def solicitar_acesso(request):
    return redirect("solicitacoes:solicitar_acesso")


@login_required
@user_passes_test(is_master)
def painel_solicitacoes(request):
    return redirect("solicitacoes:listar_solicitacoes")


@login_required
@user_passes_test(is_master)
def aprovar_solicitacao(request, id):
    # fluxo oficial de aprovar/negar é no detalhe (POST).
    return redirect("solicitacoes:detalhe_solicitacao", id=id)


@login_required
@user_passes_test(is_master)
def negar_solicitacao(request, id):
    # fluxo oficial de aprovar/negar é no detalhe (POST).
    return redirect("solicitacoes:detalhe_solicitacao", id=id)


@login_required
@user_passes_test(is_master)
def usuarios_permissoes(request):
    """
    Vai para o Django Admin do seu User customizado (contas.Usuario).
    (O /admin/auth/user/ dá 404 porque você não usa o User padrão do Django.)
    """
    try:
        return redirect(reverse("admin:contas_usuario_changelist"))
    except NoReverseMatch:
        # fallback garantido
        return redirect("/admin/contas/usuario/")
