"""URL routes for the customers app (mounted under /api/v1/customers/)."""

from rest_framework.routers import SimpleRouter

from apps.customers.views import CustomerViewSet

app_name = "customers"

router = SimpleRouter(trailing_slash=True)
router.register("", CustomerViewSet, basename="customer")

urlpatterns = router.urls
