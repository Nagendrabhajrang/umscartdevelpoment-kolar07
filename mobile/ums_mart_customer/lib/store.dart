// The app's memory: who is signed in, what is in the cart, saved items.
// Screens listen to `app` and redraw when something changes.

import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'models.dart';

final AppState app = AppState();

class AppState extends ChangeNotifier {
  static const String _guestPref = 'ums.guestCartKey.v2';

  Account? account;
  Cart cart = Cart.empty();
  Bill? bill;
  StoreSettings settings = StoreSettings(const <String, dynamic>{});
  final Set<int> wished = <int>{};

  /// Which bottom tab is open: 0 Home, 1 Categories, 2 Cart, 3 Orders, 4 Profile.
  final ValueNotifier<int> tab = ValueNotifier<int>(0);

  bool get signedIn => account != null;

  // ------------------------------------------------------------------ start

  /// Runs once when the app opens. It never throws: a server that is down
  /// still opens the app, and each screen shows its own retry message.
  Future<void> boot() async {
    try {
      await Api.init();
      Api.onUnauthorized = _sessionLost;
      try {
        account = await Api.session();
      } catch (_) {
        account = null;
      }
      if (account == null) await _useGuestKey();
      await Future.wait<void>([
        _loadSettings(),
        refreshCart(),
        refreshWishlist(),
      ]);
    } catch (_) {
      // Nothing here may stop the app from opening.
    }
  }

  Future<void> _loadSettings() async {
    try {
      settings = await Api.settings();
      notifyListeners();
    } catch (_) {}
  }

  // ------------------------------------------------------------- guest cart

  static String _newKey() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    Random random;
    try {
      random = Random.secure();
    } catch (_) {
      random = Random();
    }
    return List.generate(24, (_) => chars[random.nextInt(chars.length)]).join();
  }

  Future<void> _useGuestKey({bool fresh = false}) async {
    String? key;
    try {
      final prefs = await SharedPreferences.getInstance();
      key = fresh ? null : prefs.getString(_guestPref);
      if (key == null || key.length < 8) {
        key = _newKey();
        await prefs.setString(_guestPref, key);
      }
    } catch (_) {
      key ??= _newKey();
    }
    Api.guestKey = key;
  }

  Future<void> _dropGuestKey() async {
    Api.guestKey = null;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_guestPref);
    } catch (_) {}
  }

  // ------------------------------------------------------------------- cart

  Future<void> refreshCart() async {
    try {
      cart = await Api.cart();
      try {
        bill = await Api.cartSummary();
      } catch (_) {
        bill = null;
      }
    } catch (_) {
      // Keep what is on screen: a failed refresh is not an empty cart.
    }
    notifyListeners();
  }

  Future<void> addToCart(Product product) async {
    await Api.cartAdd(product.id);
    await refreshCart();
  }

  Future<void> setQuantity(CartLine line, int quantity) async {
    if (quantity <= 0) {
      await Api.cartRemove(line.id);
    } else {
      await Api.cartSetQuantity(line.id, quantity);
    }
    await refreshCart();
  }

  Future<void> removeLine(CartLine line) async {
    await Api.cartRemove(line.id);
    await refreshCart();
  }

  Future<void> applyCoupon(String code) async {
    await Api.couponApply(code);
    await refreshCart();
  }

  Future<void> removeCoupon() async {
    await Api.couponRemove();
    await refreshCart();
  }

  // --------------------------------------------------------------- wishlist

  Future<void> refreshWishlist() async {
    if (!signedIn) return;
    try {
      final items = await Api.wishlist();
      wished
        ..clear()
        ..addAll(items.map((e) => e.id));
      notifyListeners();
    } catch (_) {}
  }

  Future<bool> toggleWish(int productId) async {
    final saved = await Api.wishlistToggle(productId);
    if (saved) {
      wished.add(productId);
    } else {
      wished.remove(productId);
    }
    notifyListeners();
    return saved;
  }

  // ------------------------------------------------------------------ login

  /// Finishes sign-in. The guest cart is moved into the account.
  Future<void> verifyOtp(String mobile, String code) async {
    final reply = await Api.verifyOtp(mobile, code);
    Api.resetCsrf();

    final key = Api.guestKey;
    if (key != null) {
      try {
        await Api.cartMerge(key);
      } catch (_) {
        // The server already moves the cart during sign-in; this is a backup.
      }
    }
    await _dropGuestKey();

    Account? fresh;
    try {
      fresh = await Api.session();
    } catch (_) {
      fresh = null;
    }
    account = fresh ?? Account(reply);
    notifyListeners();

    await Future.wait<void>([refreshCart(), refreshWishlist()]);
  }

  Future<void> reloadAccount() async {
    try {
      final fresh = await Api.session();
      if (fresh != null) {
        account = fresh;
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> signOut() async {
    try {
      await Api.logout();
    } catch (_) {
      // Signing out on the device must always work.
    }
    if (account != null) await _becomeGuest();
  }

  void _sessionLost() {
    if (account == null) return;
    _becomeGuest();
  }

  Future<void> _becomeGuest() async {
    account = null;
    wished.clear();
    cart = Cart.empty();
    bill = null;
    notifyListeners();
    await Api.clearCookies();
    await _useGuestKey(fresh: true);
    await refreshCart();
  }
}
