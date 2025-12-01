from django.http import HttpResponseForbidden
from functools import wraps

def role_required(check_function):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if check_function(request.user):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Você não tem permissão para acessar esta página.")
        return _wrapped_view
    return decorator

# → Admin / Master
allow_admin = role_required(lambda u: u.is_superuser or u.is_master)

# → Engenheiro pode emitir
allow_emit = role_required(lambda u: u.is_superuser or u.is_master or u.is_engenheiro)

# → Revisor pode revisar
allow_review = role_required(lambda u: u.is_superuser or u.is_master or u.is_revisor)

# → Aprovador pode aprovar
allow_approve = role_required(lambda u: u.is_superuser or u.is_master or u.is_aprovador)
