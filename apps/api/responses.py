import re

from django.http import JsonResponse


class InvalidQuery(ValueError):
    pass


def error(code, message, status):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def validate_parameters(query, allowed):
    if set(query) - set(allowed):
        raise InvalidQuery("Unsupported query parameter.")
    if any(len(query.getlist(key)) != 1 for key in query):
        raise InvalidQuery("Query parameters must not be repeated.")


def positive_integer(query, name, default=None):
    if name not in query:
        return default
    value = query[name]
    if not re.fullmatch(r"[0-9]{1,19}", value):
        raise InvalidQuery(f"{name} must be a positive integer.")
    number = int(value)
    if number < 1 or number > 9223372036854775807:
        raise InvalidQuery(f"{name} must be a positive integer.")
    return number


def paginated(queryset, query, serializer):
    page = positive_integer(query, "page", 1)
    page_size = positive_integer(query, "page_size", 50)
    if page_size > 200:
        raise InvalidQuery("page_size must not exceed 200.")
    count = queryset.count()
    total_pages = max(1, (count + page_size - 1) // page_size)
    if page > total_pages:
        raise InvalidQuery("Page is out of range.")
    offset = (page - 1) * page_size
    return JsonResponse({
        "count": count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": [serializer(item) for item in queryset[offset:offset + page_size]],
    })
