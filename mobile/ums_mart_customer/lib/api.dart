// Everything that talks to the UMS Mart server lives in this one file.
//
// The backend is NOT changed by this app. It uses the same addresses the web
// storefront uses.
//
// Three rules keep every request working, signed in or not, phone or browser:
//   1. Session cookie  - kept by this file (see Api._ownCookies).
//   2. Security token  - sent as X-CSRFToken on every change (add, remove...).
//   3. Guest cart key  - sent as X-Guest-Cart on every call while not signed in.

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

class ApiConfig {
  static const String _override = String.fromEnvironment('API_BASE');

  /// `--dart-define=API_BASE=relative` : the app is served by the same web
  /// server that forwards /api to Django (serve_web.py).
  static bool get isRelative => _override == 'relative';

  static String get base {
    if (isRelative) return Uri.base.origin;
    if (_override.isNotEmpty) {
      return _override.endsWith('/')
          ? _override.substring(0, _override.length - 1)
          : _override;
    }
    if (kIsWeb) return 'http://127.0.0.1:8000';
    // The Android emulator reaches the PC through 10.0.2.2.
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }
}

/// Turns any picture address the server returns into one this device can open.
String mediaUrl(dynamic raw) {
  final value = raw == null ? '' : '$raw';
  if (value.isEmpty) return '';
  if (value.startsWith('/')) return '${ApiConfig.base}$value';
  final uri = Uri.tryParse(value);
  if (uri != null && uri.hasScheme && uri.path.startsWith('/media/')) {
    // The server may print "localhost" here, which a phone cannot open.
    return '${ApiConfig.base}${uri.path}';
  }
  return value;
}

/// Every failure reaches the screens in this one shape.
class ApiError implements Exception {
  ApiError(this.message, {this.status = 0, this.code = 'error'});

  final String message;
  final int status;
  final String code;

  factory ApiError.from(dynamic body, int status) {
    if (body is Map) {
      final err = body['error'];
      if (err is Map) {
        return ApiError(
          '${err['message'] ?? 'Something went wrong.'}',
          status: status,
          code: '${err['code'] ?? 'error'}',
        );
      }
      if (body['detail'] != null) {
        return ApiError('${body['detail']}', status: status);
      }
      if (body['message'] != null) {
        return ApiError('${body['message']}', status: status);
      }
    }
    return ApiError('Request failed (code $status). Please try again.',
        status: status);
  }

  @override
  String toString() => message;
}

/// Shows a readable sentence for any error.
String errorText(Object error) {
  if (error is ApiError) return error.message;
  return 'Something went wrong. Please try again.';
}

class ProductPage {
  ProductPage(this.items, this.hasMore);
  final List<Product> items;
  final bool hasMore;
}

class Api {
  Api._();

  static const String _cookiePref = 'ums.cookies.v2';
  static const Duration _timeout = Duration(seconds: 20);

  static final http.Client _client = http.Client();
  static final Map<String, String> _cookies = <String, String>{};
  static String? _csrf;

  /// True when this file keeps the sign-in cookie itself: always on a phone,
  /// and in the browser copy that is served by serve_web.py. A browser may
  /// refuse cookies when the app is shown inside a frame of another site (a
  /// preview panel), and then nobody could stay signed in. So the browser copy
  /// sends the cookie in the "X-App-Cookie" header and serve_web.py hands it
  /// to the server as a normal cookie.
  static bool get _ownCookies => !kIsWeb || ApiConfig.isRelative;
  static String get _cookieHeader => kIsWeb ? 'X-App-Cookie' : 'Cookie';

  /// Set while the shopper is not signed in.
  static String? guestKey;

  /// Called when the server says the session is gone.
  static void Function()? onUnauthorized;

  // ------------------------------------------------------------------ setup

  static Future<void> init() async {
    if (!_ownCookies) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_cookiePref);
      if (saved != null && saved.isNotEmpty) {
        final map = jsonDecode(saved);
        if (map is Map) {
          map.forEach((k, v) => _cookies['$k'] = '$v');
        }
      }
    } catch (_) {
      // A broken saved value only means the shopper signs in again.
    }
  }

  static Future<void> _saveCookies() async {
    if (!_ownCookies) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cookiePref, jsonEncode(_cookies));
    } catch (_) {}
  }

  static Future<void> clearCookies() async {
    _cookies.clear();
    _csrf = null;
    await _saveCookies();
  }

  static void resetCsrf() => _csrf = null;

  // ---------------------------------------------------------------- request

  static Uri _uri(String path, Map<String, dynamic>? query) {
    final uri = Uri.parse('${ApiConfig.base}$path');
    if (query == null) return uri;
    final clean = <String, String>{};
    query.forEach((key, value) {
      if (value == null) return;
      final text = '$value';
      if (text.trim().isEmpty) return;
      clean[key] = text;
    });
    return clean.isEmpty ? uri : uri.replace(queryParameters: clean);
  }

  static Future<String?> _csrfToken() async {
    if (_csrf != null) return _csrf;
    try {
      final data = await _send('GET', '/api/auth/csrf/');
      if (data is Map && data['csrf_token'] is String) {
        final token = data['csrf_token'] as String;
        if (token.isNotEmpty) _csrf = token;
      }
    } catch (_) {
      // The real request below reports the problem.
    }
    return _csrf;
  }

  static void _storeCookies(http.Response res) {
    if (!_ownCookies) return; // The browser keeps cookies by itself.
    List<String>? list;
    try {
      if (kIsWeb) {
        // serve_web.py repeats the cookies here, because a browser never
        // shows "Set-Cookie" to the app.
        final raw = res.headers['x-app-set-cookie'];
        if (raw != null && raw.isNotEmpty) {
          final parsed = jsonDecode(raw);
          if (parsed is List) list = parsed.map((e) => '$e').toList();
        }
      } else {
        list = res.headersSplitValues['set-cookie'];
      }
    } catch (_) {
      list = null;
    }
    if (list == null || list.isEmpty) return;
    var changed = false;
    for (final raw in list) {
      final first = raw.split(';').first;
      final at = first.indexOf('=');
      if (at <= 0) continue;
      final name = first.substring(0, at).trim();
      final value = first.substring(at + 1).trim();
      final lower = raw.toLowerCase();
      final expired = value.isEmpty ||
          value == '""' ||
          lower.contains('max-age=0') ||
          lower.contains('01 jan 1970') ||
          lower.contains('01-jan-1970');
      if (expired) {
        if (_cookies.remove(name) != null) changed = true;
      } else if (_cookies[name] != value) {
        _cookies[name] = value;
        changed = true;
      }
    }
    if (changed) _saveCookies();
  }

  static Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? query,
    Object? body,
    bool retry = true,
  }) async {
    final change = method != 'GET';
    final headers = <String, String>{'Accept': 'application/json'};
    final guest = guestKey;
    if (guest != null) headers['X-Guest-Cart'] = guest;
    if (_ownCookies && _cookies.isNotEmpty) {
      headers[_cookieHeader] =
          _cookies.entries.map((e) => '${e.key}=${e.value}').join('; ');
    }
    if (change) {
      final token = await _csrfToken();
      if (token != null) headers['X-CSRFToken'] = token;
      // Cookies may have been added while the token was fetched.
      if (_ownCookies && _cookies.isNotEmpty) {
        headers[_cookieHeader] =
            _cookies.entries.map((e) => '${e.key}=${e.value}').join('; ');
      }
    }

    http.Response res;
    try {
      final req = http.Request(method, _uri(path, query));
      req.headers.addAll(headers);
      if (change && (body != null || method != 'DELETE')) {
        req.headers['Content-Type'] = 'application/json';
        req.body = jsonEncode(body ?? const <String, dynamic>{});
      }
      final streamed = await _client.send(req).timeout(_timeout);
      res = await http.Response.fromStream(streamed).timeout(_timeout);
    } catch (_) {
      throw ApiError(
        'Cannot reach the server. Check that the backend is running.',
        code: 'network_error',
      );
    }

    _storeCookies(res);

    dynamic data;
    if (res.bodyBytes.isNotEmpty) {
      try {
        data = jsonDecode(utf8.decode(res.bodyBytes, allowMalformed: true));
      } catch (_) {
        data = null;
      }
    }

    if (res.statusCode >= 400) {
      final err = ApiError.from(data, res.statusCode);
      if (res.statusCode == 403 && err.code == 'csrf_failed' && retry) {
        // The token changes when the shopper signs in. Get a new one, once.
        _csrf = null;
        return _send(method, path, query: query, body: body, retry: false);
      }
      if (res.statusCode == 401) onUnauthorized?.call();
      throw err;
    }
    return data;
  }

  static Future<dynamic> _get(String path, [Map<String, dynamic>? query]) =>
      _send('GET', path, query: query);
  static Future<dynamic> _post(String path, [Object? body]) =>
      _send('POST', path, body: body);
  static Future<dynamic> _patch(String path, [Object? body]) =>
      _send('PATCH', path, body: body);
  static Future<dynamic> _delete(String path) => _send('DELETE', path);

  // ---------------------------------------------------------------- catalog

  static Future<List<Category>> categories() async {
    final data =
        await _get('/api/v1/catalog/categories/', {'page_size': 100});
    return asJsonList(data).map(Category.new).toList();
  }

  static Future<ProductPage> products({
    int page = 1,
    int pageSize = 20,
    String? search,
    int? category,
    bool featured = false,
    String? ordering,
  }) async {
    final data = await _get('/api/v1/catalog/products/', {
      'page': page,
      'page_size': pageSize,
      'search': search,
      'category': category,
      'is_featured': featured ? 'true' : null,
      'ordering': ordering,
    });
    final items = asJsonList(data).map(Product.new).toList();
    final hasMore = data is Map && data['next'] != null;
    return ProductPage(items, hasMore);
  }

  static Future<List<Product>> featured({int limit = 10}) async {
    final data = await _get(
        '/api/v1/catalog/products/featured/', {'page_size': limit});
    return asJsonList(data).map(Product.new).toList();
  }

  static Future<Product> product(int id) async =>
      Product(asJson(await _get('/api/v1/catalog/products/$id/')));

  static Future<List<Product>> related(int id) async {
    final data = await _get('/api/v1/catalog/products/$id/related/');
    return asJsonList(data).map(Product.new).toList();
  }

  static Future<List<BannerItem>> banners() async =>
      asJsonList(await _get('/api/v1/banners/live/'))
          .map(BannerItem.new)
          .toList();

  static Future<StoreSettings> settings() async =>
      StoreSettings(asJson(await _get('/api/v1/store-settings/')));

  // ------------------------------------------------------------------- cart

  static Future<Cart> cart() async => Cart(asJson(await _get('/api/v1/cart/')));

  static Future<Bill> cartSummary() async =>
      Bill(asJson(await _get('/api/v1/cart/summary/')));

  static Future<void> cartAdd(int productId, {int quantity = 1}) async {
    await _post('/api/v1/cart/items/', {
      'product': productId,
      'quantity': quantity,
      if (guestKey != null) 'guest_cart': guestKey,
    });
  }

  static Future<void> cartSetQuantity(int itemId, int quantity) async {
    await _patch('/api/v1/cart/items/$itemId/', {'quantity': quantity});
  }

  static Future<void> cartRemove(int itemId) async {
    await _delete('/api/v1/cart/items/$itemId/');
  }

  static Future<void> couponApply(String code) async {
    await _post('/api/v1/cart/coupon/', {'code': code});
  }

  static Future<void> couponRemove() async {
    await _delete('/api/v1/cart/coupon/');
  }

  static Future<void> cartMerge(String key) async {
    await _post('/api/v1/cart/merge/', {'guest_cart': key});
  }

  // ------------------------------------------------------------------ login

  static Future<Json> sendOtp(String mobile) async => asJson(
      await _post('/api/customer/send-otp/', {'mobile_number': mobile}));

  static Future<Json> resendOtp(String mobile) async => asJson(
      await _post('/api/customer/resend-otp/', {'mobile_number': mobile}));

  static Future<Json> verifyOtp(String mobile, String code) async {
    final data = await _post('/api/customer/verify-otp/', {
      'mobile_number': mobile,
      'code': code,
      if (guestKey != null) 'guest_cart': guestKey,
    });
    return asJson(data);
  }

  /// The signed-in shopper, or null for a guest.
  static Future<Account?> session() async {
    final map = asJson(await _get('/api/auth/session/'));
    if (map['authenticated'] != true) return null;
    return Account(map);
  }

  static Future<void> logout() async {
    await _post('/api/customer/logout/');
  }

  static Future<void> updateProfile({
    required String name,
    required String email,
  }) async {
    await _patch('/api/customer/profile/update/', {
      'full_name': name,
      'email': email.isEmpty ? null : email,
    });
  }

  // ----------------------------------------------------------------- orders

  static Future<List<Order>> orders() async {
    final data =
        await _get('/api/v1/orders/mine/', {'ordering': '-created_at'});
    return asJsonList(data).map(Order.new).toList();
  }

  static Future<Order> order(int id) async =>
      Order(asJson(await _get('/api/v1/orders/$id/')));

  static Future<void> cancelOrder(int id, String reason, String note) async {
    await _post('/api/v1/orders/$id/cancel/', {'reason': reason, 'note': note});
  }

  static Future<Bill> checkoutPreview({required int addressId}) async {
    final data = await _post('/api/v1/orders/checkout/preview/', {
      'address': addressId,
      'payment_method': 'cod',
    });
    return Bill(asJson(data));
  }

  static Future<Order> checkout({
    required int addressId,
    String notes = '',
  }) async {
    final data = await _post('/api/v1/orders/checkout/', {
      'address': addressId,
      'payment_method': 'cod',
      if (notes.isNotEmpty) 'customer_notes': notes,
    });
    return Order(asJson(data));
  }

  // -------------------------------------------------------------- addresses

  static Future<List<Address>> addresses() async =>
      asJsonList(await _get('/api/v1/addresses/mine/'))
          .map(Address.new)
          .toList();

  static Future<Address> addAddress(Json payload) async =>
      Address(asJson(await _post('/api/v1/addresses/mine/add/', payload)));

  static Future<void> setDefaultAddress(int id) async {
    await _post('/api/v1/addresses/$id/set-default/');
  }

  static Future<void> removeAddress(int id) async {
    await _delete('/api/v1/addresses/$id/');
  }

  // --------------------------------------------------------------- wishlist

  static Future<List<Product>> wishlist() async {
    final data = asJson(await _get('/api/v1/wishlist/'));
    return asJsonList(data['items']).map((row) {
      return Product(<String, dynamic>{
        'id': row['product'],
        'name': row['product_name'],
        'selling_price': row['selling_price'],
        'mrp': row['mrp'],
        'image_url': row['image_url'],
        'in_stock': row['in_stock'],
      });
    }).toList();
  }

  /// Returns true when the product is now saved.
  static Future<bool> wishlistToggle(int productId) async {
    final data =
        asJson(await _post('/api/v1/wishlist/toggle/', {'product': productId}));
    return data['is_wishlisted'] == true;
  }
}
