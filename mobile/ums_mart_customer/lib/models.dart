// Small read-only wrappers over the data the server sends.
// A missing value never crashes the app: it reads as empty or zero.

import 'api.dart';

typedef Json = Map<String, dynamic>;

Json asJson(dynamic v) =>
    v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};

List<Json> asJsonList(dynamic v) {
  final List<dynamic> list;
  if (v is List) {
    list = v;
  } else if (v is Map && v['results'] is List) {
    list = v['results'] as List;
  } else {
    list = const [];
  }
  return list
      .whereType<Map>()
      .map((e) => Map<String, dynamic>.from(e))
      .toList();
}

double _d(dynamic v) {
  if (v == null) return 0;
  if (v is num) return v.toDouble();
  return double.tryParse('$v') ?? 0;
}

int _i(dynamic v) {
  if (v == null) return 0;
  if (v is num) return v.toInt();
  return int.tryParse('$v') ?? 0;
}

String _s(dynamic v, [String fallback = '']) {
  if (v == null) return fallback;
  final text = '$v';
  return text.isEmpty ? fallback : text;
}

class Category {
  Category(this.json);
  final Json json;

  int get id => _i(json['id']);
  String get name => _s(json['name'], 'Category');
  int get parentId => _i(json['parent']);
  String get image => mediaUrl(json['image_url'] ?? json['image']);
  String get icon => _s(json['icon_name']);
  int get productCount => _i(json['product_count']);
  int get childCount => _i(json['child_count']);
}

class Product {
  Product(this.json);
  final Json json;

  int get id => _i(json['id']);
  String get name => _s(json['name'], 'Product');
  String get brand => _s(json['brand']);
  String get unit => _s(json['unit_label']);
  double get mrp => _d(json['mrp']);
  double get price => _d(json['selling_price']);
  int get discount {
    final fromServer = _d(json['discount_percent']);
    if (fromServer > 0) return fromServer.round();
    if (mrp > price && mrp > 0) return (((mrp - price) / mrp) * 100).round();
    return 0;
  }

  double get saving => mrp > price ? mrp - price : 0;
  String get image => mediaUrl(json['image_url'] ?? json['primary_image']);
  bool get inStock => json['in_stock'] != false;
  bool get isVeg => json['is_vegetarian'] != false;
  String get categoryName => _s(json['category_name']);
  int get categoryId => _i(json['category']);
  String get description =>
      _s(json['description'], _s(json['short_description']));

  /// Main picture first, then the extra pictures. No repeats.
  List<String> get gallery {
    final out = <String>[];
    void add(dynamic raw) {
      final url = mediaUrl(raw);
      if (url.isNotEmpty && !out.contains(url)) out.add(url);
    }

    add(json['image_url'] ?? json['primary_image']);
    for (final row in asJsonList(json['images'])) {
      add(row['image']);
    }
    return out;
  }
}

class CartLine {
  CartLine(this.json);
  final Json json;

  int get id => _i(json['id']);
  int get productId => _i(json['product']);
  String get name => _s(json['product_name'], 'Item');
  String get unit => _s(json['unit_label']);
  String get image => mediaUrl(json['product_image']);
  int get quantity => _i(json['quantity']);
  double get unitPrice => _d(json['unit_price']);
  double get unitMrp => _d(json['unit_mrp']);
  double get total => _d(json['line_total']);
  bool get available => json['is_available'] != false;
}

class Cart {
  Cart(this.json) : lines = asJsonList(json['items']).map(CartLine.new).toList();
  factory Cart.empty() => Cart(const <String, dynamic>{});

  final Json json;
  final List<CartLine> lines;

  bool get isEmpty => lines.isEmpty;
  int get count {
    final fromServer = _i(json['total_quantity']);
    if (fromServer > 0) return fromServer;
    return lines.fold<int>(0, (sum, l) => sum + l.quantity);
  }

  double get subtotal => _d(json['subtotal']);
  String get coupon => _s(json['coupon_code']);
}

/// The bill: item total, discount, delivery, tax and the amount to pay.
class Bill {
  Bill(this.json);
  final Json json;

  double get subtotal => _d(json['subtotal']);
  double get mrpTotal => _d(json['mrp_total']);
  double get productSavings => _d(json['product_savings'] ?? json['savings']);
  double get discount => _d(json['discount_amount']);
  double get delivery => _d(json['delivery_charge']);
  double get packaging => _d(json['packaging_charge']);
  double get tax => _d(json['tax_amount']);
  double get total => _d(json['grand_total']);
  String get coupon => _s(json['coupon_code']);
  double get toFreeDelivery => _d(json['amount_to_free_delivery']);
  double get minimumOrder => _d(json['minimum_order_value']);
  bool get minimumMet => json['minimum_order_met'] != false;
  bool get storeOpen => json['store_open'] != false;
  double get totalSavings => productSavings + discount;

  /// Problems the server found, in plain sentences.
  List<String> get issues {
    final raw = json['issues'];
    if (raw is! List) return const [];
    return raw
        .map((e) => e is Map ? _s(e['message']) : '$e')
        .where((e) => e.isNotEmpty)
        .toList();
  }
}

class BannerItem {
  BannerItem(this.json);
  final Json json;

  int get id => _i(json['id']);
  String get title => _s(json['title']);
  String get subtitle => _s(json['subtitle']);
  String get image => mediaUrl(json['mobile_image_url'] ??
      json['image_url'] ??
      json['mobile_image'] ??
      json['image']);
  int get productId => _i(json['linked_product']);
  int get categoryId => _i(json['linked_category']);
  String get coupon => _s(json['linked_coupon_code']);
}

class StoreSettings {
  StoreSettings(this.json);
  final Json json;

  String get name => _s(json['store_name'], 'UMS Mart');
  String get tagline => _s(json['tagline'], 'Fresh groceries to your door');
  String get phone => _s(json['contact_phone']);
  String get email => _s(json['contact_email']);
  String get address => _s(json['address']);
  double get freeDeliveryAbove => _d(json['free_delivery_threshold']);
  int get etaMinutes {
    final value = _i(json['delivery_eta_minutes']);
    return value == 0 ? 45 : value;
  }

  bool get storeOpen => json['is_store_open'] != false;
}

class Address {
  Address(this.json);
  final Json json;

  int get id => _i(json['id']);
  String get label => _s(json['label_display'], _s(json['label'], 'Home'));
  String get labelKey => _s(json['label'], 'home');
  String get recipient => _s(json['recipient_name']);
  String get mobile => _s(json['recipient_mobile']);
  bool get isDefault => json['is_default'] == true;

  String get full {
    final ready = _s(json['full_address']);
    if (ready.isNotEmpty) return ready;
    return [
      _s(json['line1']),
      _s(json['line2']),
      _s(json['landmark']),
      _s(json['city']),
      _s(json['state']),
      _s(json['pincode']),
    ].where((e) => e.isNotEmpty).join(', ');
  }
}

class OrderLine {
  OrderLine(this.json);
  final Json json;

  String get name => _s(json['product_name'], 'Item');
  String get unit => _s(json['unit_label']);
  int get quantity => _i(json['quantity']);
  double get total => _d(json['line_total']);
  String get image => mediaUrl(json['product_image_url']);
}

class Order {
  Order(this.json);
  final Json json;

  static const List<String> steps = [
    'pending',
    'packed',
    'out_for_delivery',
    'delivered',
  ];

  static const Map<String, String> labels = {
    'pending': 'Order placed',
    'packed': 'Packed',
    'out_for_delivery': 'Out for delivery',
    'delivered': 'Delivered',
    'cancelled': 'Cancelled',
    'returned': 'Returned',
    'refunded': 'Refunded',
  };

  int get id => _i(json['id']);
  String get number => _s(json['order_number'], 'Order');
  String get status => _s(json['status'], 'pending');
  String get statusLabel => labels[status] ?? _s(json['status_display'], status);
  bool get isClosed =>
      status == 'cancelled' || status == 'returned' || status == 'refunded';
  bool get isDelivered => status == 'delivered';
  int get stepIndex => steps.indexOf(status);

  String get paymentLabel =>
      _s(json['payment_method_display'], 'Cash on delivery');
  String get paymentStatus =>
      _s(json['payment_status_display'], json['is_paid'] == true ? 'Paid' : '');

  double get total => _d(json['grand_total']);
  double get subtotal => _d(json['subtotal']);
  double get discount => _d(json['discount_amount']);
  double get delivery => _d(json['delivery_charge']);
  double get packaging => _d(json['packaging_charge']);
  double get tax => _d(json['tax_amount']);
  double get savings => _d(json['total_savings']);
  int get itemCount => _i(json['item_count']);
  DateTime? get createdAt => DateTime.tryParse(_s(json['created_at']))?.toLocal();
  bool get canCancel => json['can_be_cancelled'] == true;

  String get recipient => _s(json['delivery_recipient_name']);
  String get recipientMobile => _s(json['delivery_recipient_mobile']);
  String get address =>
      _s(json['full_delivery_address'], _s(json['delivery_city']));
  String get notes => _s(json['customer_notes']);

  List<OrderLine> get lines =>
      asJsonList(json['items']).map(OrderLine.new).toList();
}

class Account {
  Account(this.json);
  final Json json;

  Json get _user {
    final u = json['user'];
    return u is Map ? Map<String, dynamic>.from(u) : json;
  }

  String get name => _s(_user['display_name'] ?? _user['full_name']);
  String get mobile => _s(_user['mobile_number']);
  String get email => _s(_user['email']);

  String get initials {
    final parts =
        name.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return 'U';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }
}
