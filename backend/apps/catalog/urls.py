"""URL routes for the catalog app."""

from rest_framework.routers import SimpleRouter

from apps.catalog.views import CategoryViewSet, ProductImageViewSet, ProductViewSet

app_name = "catalog"

router = SimpleRouter(trailing_slash=True)
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("product-images", ProductImageViewSet, basename="product-image")

urlpatterns = router.urls
