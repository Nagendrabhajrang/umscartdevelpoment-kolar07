"""URL routes for the banners app."""

from rest_framework.routers import SimpleRouter

from apps.banners.views import BannerViewSet

app_name = "banners"

router = SimpleRouter(trailing_slash=True)
router.register("", BannerViewSet, basename="banner")

urlpatterns = router.urls
