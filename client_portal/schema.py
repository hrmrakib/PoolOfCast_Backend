"""drf-spectacular helpers for documenting client_portal's views.

Every view in this app wraps its payload in one of two hand-rolled envelopes
instead of returning a serializer's data directly (see views.py's
success_response/error_response and core.pagination.CustomPagination). These
helpers model those envelopes accurately for the OpenAPI schema without
changing any runtime behavior.
"""

from rest_framework import serializers
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, inline_serializer

GUEST_TOKEN_PARAMETER = OpenApiParameter(
    name="X-Guest-Token",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description=(
        "The guest's session token, returned by the identify/session endpoints. "
        "A 'Bearer <token>' prefix is also accepted."
    ),
)


def envelope(name, data_field=None, message_example="Request successful."):
    """Models the {status, status_code, message, data} shape used by success_response/error_response."""
    fields = {
        "status": serializers.BooleanField(default=True),
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(default=message_example),
    }
    if data_field is not None:
        fields["data"] = data_field
    return inline_serializer(name=name, fields=fields)


ERROR_RESPONSE = envelope(
    "ClientPortalErrorResponse",
    message_example="A description of what went wrong.",
)


def paginated_envelope(name, data_field):
    """Models core.pagination.CustomPagination's {success, message, request_id, meta, data} shape."""
    meta = inline_serializer(
        name=f"{name}Meta",
        fields={
            "total_items": serializers.IntegerField(),
            "total_pages": serializers.IntegerField(),
            "current_page": serializers.IntegerField(),
            "next": serializers.CharField(allow_null=True),
            "previous": serializers.CharField(allow_null=True),
            "per_page": serializers.IntegerField(),
        },
    )
    return inline_serializer(
        name=name,
        fields={
            "success": serializers.BooleanField(default=True),
            "message": serializers.CharField(default="Data fetched successfully!"),
            "request_id": serializers.CharField(allow_null=True),
            "meta": meta,
            "data": data_field,
        },
    )
