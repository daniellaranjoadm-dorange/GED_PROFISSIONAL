from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.automacoes.models import AutomationExecutionLock


DEFAULT_LOCK_HOURS = 6


def adquirir_bloqueio(nome, usuario=None, horas=DEFAULT_LOCK_HOURS):
    """Adquire um bloqueio exclusivo; retorna (lock, bloqueio_existente)."""
    agora = timezone.now()
    token = uuid4()
    usuario = usuario if getattr(usuario, "is_authenticated", False) else None

    try:
        with transaction.atomic():
            existente = (
                AutomationExecutionLock.objects.select_for_update()
                .filter(nome=nome)
                .first()
            )
            if existente and existente.expira_em > agora:
                return None, existente

            if existente:
                existente.token = token
                existente.usuario = usuario
                existente.adquirido_em = agora
                existente.expira_em = agora + timedelta(hours=horas)
                existente.save(
                    update_fields=["token", "usuario", "adquirido_em", "expira_em"]
                )
                return existente, None

            novo = AutomationExecutionLock.objects.create(
                nome=nome,
                token=token,
                usuario=usuario,
                expira_em=agora + timedelta(hours=horas),
            )
            return novo, None
    except IntegrityError:
        return None, AutomationExecutionLock.objects.filter(nome=nome).first()


def liberar_bloqueio(lock):
    if lock is None:
        return False
    apagados, _ = AutomationExecutionLock.objects.filter(
        pk=lock.pk,
        token=lock.token,
    ).delete()
    return bool(apagados)
