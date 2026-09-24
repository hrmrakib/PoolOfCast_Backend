from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

try:
    from core.logging_context import get_request_id
except ModuleNotFoundError:
    def get_request_id():
        return None


class CustomPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 1000

    def get_paginated_response(self, data):
        return Response(
            {
                "success": True,
                "message": "Data fetched successfully!",
                "request_id": get_request_id(),
                "meta": {
                    "total_items": self.page.paginator.count,
                    "total_pages": self.page.paginator.num_pages,
                    "current_page": self.page.number,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "per_page": self.page_size,
                },
                "data": data,
            }
        )
