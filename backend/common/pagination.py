"""Pagination classes shared by every list endpoint."""

from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """Page-number pagination with ``page`` / ``page_size`` query parameters."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200
    page_query_param = "page"


class LargeResultsSetPagination(StandardResultsSetPagination):
    page_size = 100
    max_page_size = 500


class SmallResultsSetPagination(StandardResultsSetPagination):
    page_size = 10
    max_page_size = 50


class NoPagination(PageNumberPagination):
    page_size = None


class EnvelopePagination(StandardResultsSetPagination):
    """Pagination that wraps results in a stable ``data`` envelope.

    Kept for clients that prefer ``{"data": [...], "meta": {...}}`` over the
    DRF default ``{"count", "next", "previous", "results"}`` shape.
    """

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    (
                        "meta",
                        OrderedDict(
                            [
                                ("count", self.page.paginator.count),
                                ("page", self.page.number),
                                ("page_size", self.get_page_size(self.request)),
                                ("total_pages", self.page.paginator.num_pages),
                                ("next", self.get_next_link()),
                                ("previous", self.get_previous_link()),
                            ]
                        ),
                    ),
                    ("data", data),
                ]
            )
        )
