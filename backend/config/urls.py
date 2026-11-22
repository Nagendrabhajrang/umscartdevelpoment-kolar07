"""
UMS Mart root URL configuration.

Everything the clients consume lives under /api/v1/. The base URL prefix is
applied once here so that a future /api/v2/ can be introduced side by side
without touching any app-level urls.py.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from django.views.decorators.cache import never_cache
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

admin.site.site_header = "UMS Mart Administration"
admin.site.site_title = "UMS Mart Admin"
admin.site.index_title = "UMS Mart - Store Operations"


@never_cache
def health_check(request):
    """Liveness probe used by Nginx/systemd/monitoring."""
    from django.db import connection

    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover - only on broken DB
        database_ok = False

    payload = {
        "status": "ok" if database_ok else "degraded",
        "service": "ums-mart-api",
        "version": "1.0.0",
        "database": "up" if database_ok else "down",
    }
    return JsonResponse(payload, status=200 if database_ok else 503)


# Endpoints advertised on the root page and the /api/v1/ index. Kept explicit
# rather than reverse()d because the index is documentation, not routing.
API_SECTIONS = [
    ("Customers", "/api/v1/customers/"),
    ("Catalog", "/api/v1/catalog/"),
    ("Inventory", "/api/v1/inventory/"),
    ("Cart", "/api/v1/cart/"),
    ("Wishlist", "/api/v1/wishlist/"),
    ("Addresses", "/api/v1/addresses/"),
    ("Orders", "/api/v1/orders/"),
    ("Payments", "/api/v1/payments/"),
    ("Promotions", "/api/v1/promotions/"),
    ("Banners", "/api/v1/banners/"),
    ("Store settings", "/api/v1/store-settings/"),
]


@never_cache
def api_index(request):
    """Human-readable landing page.

    The API has no HTML client of its own — the storefront and the admin
    console are separate Vite apps. Without this, opening the bare host in a
    browser returns a bare 404, which looks like a broken deployment.
    """
    counts = {}
    try:
        from apps.catalog.models import Product
        from apps.customers.models import Customer
        from apps.orders.models import Order

        counts = {
            "products": Product.objects.count(),
            "customers": Customer.objects.count(),
            "orders": Order.objects.count(),
        }
    except Exception:  # pragma: no cover - landing page must never 500
        counts = {}

    stats_html = "".join(
        f'<div class="stat"><span class="n">{value}</span>'
        f'<span class="l">{label}</span></div>'
        for label, value in [
            ("products", counts.get("products", "—")),
            ("customers", counts.get("customers", "—")),
            ("orders", counts.get("orders", "—")),
        ]
    )

    rows_html = "".join(
        f'<tr><td><a href="{href}">{name}</a></td><td class="path">{href}</td></tr>'
        for name, href in API_SECTIONS
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UMS Mart &middot; API</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system,
         "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #0f172a;
         line-height: 1.55; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 40px 20px 64px; }}
  .brand {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  .logo {{ width: 44px; height: 44px; border-radius: 12px; background: #4f46e5;
          display: grid; place-items: center; color: #fff; font-weight: 700;
          font-size: 18px; }}
  h1 {{ font-size: 26px; margin: 0; letter-spacing: -0.02em; }}
  .sub {{ color: #64748b; font-size: 14px; margin: 0 0 28px; }}
  .ok {{ display: inline-flex; align-items: center; gap: 7px; background: #ecfdf5;
        border: 1px solid #a7f3d0; color: #065f46; padding: 5px 12px;
        border-radius: 999px; font-size: 13px; font-weight: 600; }}
  .dot {{ width: 7px; height: 7px; border-radius: 50%; background: #10b981; }}
  .stats {{ display: flex; gap: 12px; margin: 24px 0 28px; flex-wrap: wrap; }}
  .stat {{ flex: 1; min-width: 130px; background: #fff; border: 1px solid #e2e8f0;
          border-radius: 12px; padding: 14px 16px; }}
  .stat .n {{ display: block; font-size: 24px; font-weight: 700; }}
  .stat .l {{ font-size: 12px; color: #64748b; text-transform: uppercase;
             letter-spacing: .04em; }}
  .cards {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
           margin-bottom: 32px; }}
  .card {{ display: block; background: #fff; border: 1px solid #e2e8f0;
          border-radius: 12px; padding: 16px; text-decoration: none;
          color: inherit; transition: border-color .15s, transform .15s; }}
  .card:hover {{ border-color: #6366f1; transform: translateY(-1px); }}
  .card strong {{ display: block; font-size: 15px; margin-bottom: 3px; }}
  .card span {{ font-size: 13px; color: #64748b; }}
  h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .06em;
       color: #64748b; margin: 0 0 10px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
          border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;
          font-size: 14px; }}
  td {{ padding: 10px 16px; border-bottom: 1px solid #f1f5f9; }}
  tr:last-child td {{ border-bottom: 0; }}
  tr:hover td {{ background: #f8fafc; }}
  a {{ color: #4f46e5; }}
  .path {{ color: #94a3b8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 13px; text-align: right; }}
  footer {{ margin-top: 32px; font-size: 12px; color: #94a3b8; }}
  .warn {{ margin-top: 24px; background: #fffbeb; border: 1px solid #fde68a;
          color: #92400e; border-radius: 12px; padding: 12px 16px; font-size: 13px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <div class="logo">UMS</div>
    <div>
      <h1>UMS Mart API</h1>
    </div>
  </div>
  <p class="sub">Grocery store back end &middot; Django {settings.VERSION if hasattr(settings, "VERSION") else ""}</p>
  <span class="ok"><span class="dot"></span> Service healthy &middot; database connected</span>

  <div class="stats">{stats_html}</div>

  <div class="cards">
    <a class="card" href="/api/docs/">
      <strong>Swagger docs &rarr;</strong>
      <span>Browse and call every endpoint</span>
    </a>
    <a class="card" href="/api/redoc/">
      <strong>ReDoc &rarr;</strong>
      <span>Readable API reference</span>
    </a>
    <a class="card" href="/api/schema/">
      <strong>OpenAPI schema &rarr;</strong>
      <span>Machine-readable YAML</span>
    </a>
    <a class="card" href="/admin/">
      <strong>Django admin &rarr;</strong>
      <span>Database browser</span>
    </a>
  </div>

  <h2>Endpoints</h2>
  <table>{rows_html}</table>

  <div class="warn">
    <strong>No authentication is enabled in this build.</strong> Every endpoint is
    open to anyone who can reach this port. Keep it on localhost.
  </div>

  <footer>
    Storefront runs separately on <code>http://localhost:5173</code> &middot;
    admin console on <code>http://localhost:5174</code> &middot;
    health probe at <a href="/health/">/health/</a>
  </footer>
</div>
</body>
</html>"""
    return HttpResponse(html)


@never_cache
def api_v1_index(request):
    """JSON index of the v1 surface, so a bare GET /api/v1/ is not a 404."""
    return JsonResponse(
        {
            "service": "ums-mart-api",
            "version": "v1",
            "sections": {name: href for name, href in API_SECTIONS},
            "docs": "/api/docs/",
            "schema": "/api/schema/",
            "health": "/health/",
        },
        json_dumps_params={"indent": 2},
    )


API_V1_PATTERNS = (
    [
        path("customers/", include("apps.customers.urls")),
        path("catalog/", include("apps.catalog.urls")),
        path("inventory/", include("apps.inventory.urls")),
        path("cart/", include("apps.cart.urls")),
        path("wishlist/", include("apps.wishlist.urls")),
        path("addresses/", include("apps.addresses.urls")),
        path("orders/", include("apps.orders.urls")),
        path("payments/", include("apps.payments.urls")),
        path("promotions/", include("apps.promotions.urls")),
        path("banners/", include("apps.banners.urls")),
        path("store-settings/", include("apps.store_settings.urls")),
    ],
    "v1",
)

# Authentication lives at the bare /api/ prefix, exactly as specified, so the
# paths stay short and stable: /api/admin/login/, /api/customer/send-otp/, etc.
urlpatterns_auth = [
    path("api/admin/", include("apps.authentication.urls_admin")),
    path("api/customer/", include("apps.authentication.urls_customer")),
    path("api/auth/", include("apps.authentication.urls_shared")),
]

urlpatterns = [
    path("", api_index, name="api-index"),
    path("admin/", admin.site.urls),
    path("api/v1/", api_v1_index, name="api-v1-index"),
    path("api/v1/", include(API_V1_PATTERNS, namespace="v1")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="api-schema"),
        name="redoc",
    ),
    path("health/", health_check, name="health-check"),
]

urlpatterns += urlpatterns_auth

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
