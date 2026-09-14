from functools import wraps

from apps.contas.permissions import usuario_tem_permissao

from .responses import InvalidQuery, error



def document_center_read_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "GET":
            response = error("method_not_allowed", "Only GET is supported.", 405)
            response["Allow"] = "GET"
        elif not request.user.is_authenticated:
            response = error(
                "authentication_required",
                "Authentication required.",
                401,
            )
        elif not usuario_tem_permissao(
            request.user,
            "automacoes.visualizar",
        ):
            response = error(
                "permission_denied",
                "Permission denied.",
                403,
            )
        else:
            try:
                response = view(request, *args, **kwargs)
            except InvalidQuery as exc:
                response = error("invalid_query", str(exc), 400)

        response["Cache-Control"] = "private, no-store"
        return response

    return wrapped

def core_read_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "GET":
            response = error("method_not_allowed", "Only GET is supported.", 405)
            response["Allow"] = "GET"
        elif not request.user.is_authenticated:
            response = error("authentication_required", "Authentication required.", 401)
        elif not usuario_tem_permissao(request.user, "ged.visualizar"):
            response = error("permission_denied", "Permission denied.", 403)
        else:
            try:
                response = view(request, *args, **kwargs)
            except InvalidQuery as exc:
                response = error("invalid_query", str(exc), 400)
        response["Cache-Control"] = "private, no-store"
        return response
    return wrapped
