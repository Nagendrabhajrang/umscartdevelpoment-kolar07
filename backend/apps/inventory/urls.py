"""URL routes for the inventory app."""

from rest_framework.routers import SimpleRouter

from apps.inventory.views import InventoryLogViewSet, StockViewSet

app_name = "inventory"

router = SimpleRouter(trailing_slash=True)
router.register("stock", StockViewSet, basename="stock")
router.register("movements", InventoryLogViewSet, basename="movement")

urlpatterns = router.urls
