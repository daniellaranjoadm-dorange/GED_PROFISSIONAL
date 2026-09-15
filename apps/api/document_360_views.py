from django.http import JsonResponse

from apps.automacoes.services.document_360 import consultar_documento_360
from .document_360_serializers import serialize_document_360
from .permissions import document_center_read_only
from .responses import error, validate_parameters


@document_center_read_only
def document_360_detail(request, document_id):
    validate_parameters(request.GET, set())
    document = consultar_documento_360(document_id)
    if document is None:
        return error("not_found", "Document not found.", 404)
    return JsonResponse(serialize_document_360(document))
