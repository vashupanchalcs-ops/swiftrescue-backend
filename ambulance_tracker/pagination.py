"""Small, dependency-free list pagination used by the legacy JSON endpoints.

Existing clients receive the historical array response by default.  Clients
that opt into ``paginate=1`` (or send ``page``/``page_size``) receive a stable
envelope with metadata, so pagination can be rolled out screen by screen.
"""

from django.http import JsonResponse


TRUE_VALUES = {"1", "true", "yes", "on"}


def parse_list_options(request, default_page_size=50, max_page_size=200):
    params = request.GET
    try:
        page = max(1, int(params.get("page", "1")))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(params.get("page_size", default_page_size))
    except (TypeError, ValueError):
        page_size = default_page_size
    page_size = max(1, min(max_page_size, page_size))
    paginate = (
        str(params.get("paginate", "")).strip().lower() in TRUE_VALUES
        or "page" in params
        or "page_size" in params
    )
    return page, page_size, paginate


def list_response(request, queryset, serializer, *, default_page_size=50, max_page_size=200):
    page, page_size, paginate = parse_list_options(request, default_page_size, max_page_size)
    if not paginate:
        return JsonResponse([serializer(item) for item in queryset], safe=False)

    total = queryset.count()
    start = (page - 1) * page_size
    rows = queryset[start : start + page_size]
    return JsonResponse({
        "results": [serializer(item) for item in rows],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "has_next": start + page_size < total,
            "has_previous": page > 1,
        },
    })
