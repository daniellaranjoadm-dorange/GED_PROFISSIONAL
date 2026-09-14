from django.http import JsonResponse

from . import selectors
from .permissions import core_read_only
from .responses import InvalidQuery, error, paginated, positive_integer, validate_parameters
from .serializers import serialize_document, serialize_project


@core_read_only
def project_list(request):
    validate_parameters(request.GET, {"page", "page_size"})
    return paginated(selectors.projects(), request.GET, serialize_project)


@core_read_only
def project_detail(request, id):
    validate_parameters(request.GET, set())
    project = selectors.projects().filter(pk=id).first()
    if project is None:
        return error("not_found", "Project not found.", 404)
    return JsonResponse(serialize_project(project))


@core_read_only
def document_list(request):
    validate_parameters(request.GET, {"page", "page_size", "project_id"})
    queryset = selectors.documents()
    project_id = positive_integer(request.GET, "project_id")
    if project_id is not None:
        if not selectors.projects().filter(pk=project_id).exists():
            raise InvalidQuery("Project does not exist.")
        queryset = queryset.filter(projeto_id=project_id)
    return paginated(queryset, request.GET, serialize_document)


@core_read_only
def document_detail(request, id):
    validate_parameters(request.GET, set())
    document = selectors.documents().filter(pk=id).first()
    if document is None:
        return error("not_found", "Document not found.", 404)
    return JsonResponse(serialize_document(document))
