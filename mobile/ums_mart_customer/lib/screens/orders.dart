// Orders tab (list) and one order's page (status, items, bill, cancel).

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../store.dart';
import '../ui.dart';

Color _statusColor(Order o) {
  if (o.isClosed) return C.rose;
  if (o.isDelivered) return C.brand;
  if (o.status == 'out_for_delivery') return C.blue;
  return const Color(0xFFB45309);
}

Color _statusSoft(Order o) {
  if (o.isClosed) return C.roseSoft;
  if (o.isDelivered) return C.brandSoft;
  if (o.status == 'out_for_delivery') return const Color(0xFFEAF1FF);
  return C.amberSoft;
}

class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: _statusSoft(order),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        order.statusLabel,
        style: TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w900,
          color: _statusColor(order),
        ),
      ),
    );
  }
}

class OrdersTab extends StatefulWidget {
  const OrdersTab({super.key});

  @override
  State<OrdersTab> createState() => _OrdersTabState();
}

class _OrdersTabState extends State<OrdersTab> {
  List<Order> _orders = const [];
  bool _loading = false;
  String? _error;
  bool _wasSignedIn = false;

  @override
  void initState() {
    super.initState();
    _wasSignedIn = app.signedIn;
    app.addListener(_appChanged);
    app.tab.addListener(_tabChanged);
    if (app.signedIn) _load();
  }

  @override
  void dispose() {
    app.removeListener(_appChanged);
    app.tab.removeListener(_tabChanged);
    super.dispose();
  }

  void _appChanged() {
    if (app.signedIn == _wasSignedIn) return;
    _wasSignedIn = app.signedIn;
    if (app.signedIn) {
      _load();
    } else if (mounted) {
      setState(() => _orders = const []);
    }
  }

  void _tabChanged() {
    if (app.tab.value == 3 && app.signedIn) _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = _orders.isEmpty;
      _error = null;
    });
    try {
      final list = await Api.orders();
      if (!mounted) return;
      setState(() {
        _orders = list;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = errorText(e);
        _loading = false;
      });
    }
  }

  Future<void> _open(Order o) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => OrderScreen(orderId: o.id)),
    );
    if (mounted && app.signedIn) _load();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        Widget body;
        if (!app.signedIn) {
          body = Notice(
            icon: Icons.receipt_long_outlined,
            title: 'Sign in to see your orders',
            text: 'Track deliveries and reorder your favourites.',
            button: 'Sign in',
            onButton: () => requireLogin(context),
          );
        } else if (_loading) {
          body = const Loading();
        } else if (_error != null && _orders.isEmpty) {
          body = Notice(
            icon: Icons.wifi_off_rounded,
            title: 'Could not load your orders',
            text: _error!,
            button: 'Try again',
            onButton: _load,
          );
        } else if (_orders.isEmpty) {
          body = Notice(
            icon: Icons.receipt_long_outlined,
            title: 'No orders yet',
            text: 'Your orders will show up here after you place one.',
            button: 'Start shopping',
            onButton: () => app.tab.value = 0,
          );
        } else {
          body = RefreshIndicator(
            color: C.brand,
            onRefresh: _load,
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
              itemCount: _orders.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) => _card(_orders[i]),
            ),
          );
        }
        return Scaffold(
          appBar: AppBar(title: const Text('My orders')),
          body: body,
        );
      },
    );
  }

  Widget _card(Order o) {
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: C.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => _open(o),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    height: 44,
                    width: 44,
                    decoration: BoxDecoration(
                      color: _statusSoft(o),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(
                      o.isClosed
                          ? Icons.cancel_outlined
                          : o.isDelivered
                              ? Icons.check_circle_outline_rounded
                              : Icons.local_shipping_outlined,
                      color: _statusColor(o),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          o.number,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w900,
                            color: C.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          dateText(o.createdAt),
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: C.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                  StatusChip(order: o),
                ],
              ),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Divider(),
              ),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '${o.itemCount} ${o.itemCount == 1 ? 'item' : 'items'}  •  ${o.paymentLabel}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: C.body,
                      ),
                    ),
                  ),
                  Text(
                    money(o.total),
                    style: const TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w900,
                      color: C.ink,
                    ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.chevron_right_rounded, color: C.muted),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// --------------------------------------------------------------- one order

class OrderScreen extends StatefulWidget {
  const OrderScreen({super.key, required this.orderId});

  final int orderId;

  @override
  State<OrderScreen> createState() => _OrderScreenState();
}

class _OrderScreenState extends State<OrderScreen> {
  Order? _order;
  String? _error;
  bool _cancelling = false;

  static const Map<String, String> _reasons = {
    'customer_request': 'I changed my mind',
    'address_issue': 'Wrong delivery address',
    'other': 'Another reason',
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final order = await Api.order(widget.orderId);
      if (mounted) {
        setState(() {
          _order = order;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    }
  }

  Future<void> _cancel() async {
    var reason = 'customer_request';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocal) => AlertDialog(
          backgroundColor: Colors.white,
          surfaceTintColor: Colors.transparent,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
          title: const Text(
            'Cancel this order?',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
          contentPadding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final entry in _reasons.entries)
                InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: () => setLocal(() => reason = entry.key),
                  child: Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
                    child: Row(
                      children: [
                        Icon(
                          reason == entry.key
                              ? Icons.radio_button_checked_rounded
                              : Icons.radio_button_off_rounded,
                          color: reason == entry.key ? C.brand : C.muted,
                          size: 22,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            entry.value,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              color: C.ink,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              style: TextButton.styleFrom(foregroundColor: C.muted),
              child: const Text('Keep order'),
            ),
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              style: TextButton.styleFrom(foregroundColor: C.rose),
              child: const Text('Cancel order'),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _cancelling = true);
    try {
      await Api.cancelOrder(widget.orderId, reason, _reasons[reason] ?? '');
      await _load();
      if (mounted) toast(context, 'Order cancelled');
    } catch (e) {
      if (mounted) toast(context, errorText(e));
    } finally {
      if (mounted) setState(() => _cancelling = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final o = _order;
    return Scaffold(
      appBar: AppBar(title: const Text('Order details')),
      body: o == null
          ? (_error == null
              ? const Loading()
              : Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not load this order',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                ))
          : RefreshIndicator(
              color: C.brand,
              onRefresh: _load,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                children: [
                  _summary(o),
                  const SizedBox(height: 14),
                  if (!o.isClosed) ...[
                    _progress(o),
                    const SizedBox(height: 14),
                  ],
                  _items(o),
                  const SizedBox(height: 14),
                  _bill(o),
                  if (o.isUpi) ...[
                    const SizedBox(height: 14),
                    _upi(o),
                  ],
                  const SizedBox(height: 14),
                  _delivery(o),
                  if (o.canCancel) ...[
                    const SizedBox(height: 18),
                    OutlinedButton(
                      onPressed: _cancelling ? null : _cancel,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: C.rose,
                        side: const BorderSide(color: C.rose, width: 1.3),
                        minimumSize: const Size(double.infinity, 50),
                      ),
                      child: Text(
                          _cancelling ? 'Cancelling...' : 'Cancel this order'),
                    ),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _summary(Order o) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _statusSoft(o),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  o.statusLabel,
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                    color: _statusColor(o),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  o.number,
                  style: const TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w800,
                    color: C.ink,
                  ),
                ),
                Text(
                  dateText(o.createdAt),
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: C.body,
                  ),
                ),
              ],
            ),
          ),
          Icon(
            o.isClosed
                ? Icons.cancel_rounded
                : o.isDelivered
                    ? Icons.check_circle_rounded
                    : Icons.local_shipping_rounded,
            size: 44,
            color: _statusColor(o),
          ),
        ],
      ),
    );
  }

  Widget _progress(Order o) {
    final current = o.stepIndex < 0 ? 0 : o.stepIndex;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 6),
      decoration: cardBox(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Order progress',
            style: TextStyle(
                fontSize: 15, fontWeight: FontWeight.w900, color: C.ink),
          ),
          const SizedBox(height: 14),
          for (var i = 0; i < Order.steps.length; i++)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Column(
                  children: [
                    Container(
                      height: 22,
                      width: 22,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i <= current ? C.brand : Colors.white,
                        border: Border.all(
                          color: i <= current ? C.brand : C.line,
                          width: 2,
                        ),
                      ),
                      child: i <= current
                          ? const Icon(Icons.check_rounded,
                              size: 14, color: Colors.white)
                          : null,
                    ),
                    if (i < Order.steps.length - 1)
                      Container(
                        height: 22,
                        width: 2,
                        color: i < current ? C.brand : C.line,
                      ),
                  ],
                ),
                const SizedBox(width: 12),
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(
                    Order.labels[Order.steps[i]] ?? Order.steps[i],
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight:
                          i == current ? FontWeight.w900 : FontWeight.w600,
                      color: i <= current ? C.ink : C.muted,
                    ),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _items(Order o) {
    final lines = o.lines;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardBox(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Items (${lines.length})',
            style: const TextStyle(
                fontSize: 15, fontWeight: FontWeight.w900, color: C.ink),
          ),
          const SizedBox(height: 6),
          for (final line in lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  SizedBox(
                    height: 50,
                    width: 50,
                    child: NetImage(line.image, label: line.name, radius: 12),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          line.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                            color: C.ink,
                          ),
                        ),
                        Text(
                          line.unit.isEmpty
                              ? 'Qty ${line.quantity}'
                              : '${line.unit}  •  Qty ${line.quantity}',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: C.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    money(line.total),
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w900,
                      color: C.ink,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _bill(Order o) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardBox(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Bill details',
            style: TextStyle(
                fontSize: 15, fontWeight: FontWeight.w900, color: C.ink),
          ),
          const SizedBox(height: 8),
          BillRow('Item total', money(o.subtotal)),
          if (o.discount > 0)
            BillRow('Discount', '- ${money(o.discount)}', color: C.brand),
          BillRow(
            'Delivery',
            o.delivery == 0 ? 'FREE' : money(o.delivery),
            color: o.delivery == 0 ? C.brand : null,
          ),
          if (o.packaging > 0) BillRow('Packaging', money(o.packaging)),
          if (o.tax > 0) BillRow('Taxes', money(o.tax)),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Divider(),
          ),
          BillRow('Total', money(o.total), bold: true),
          const SizedBox(height: 6),
          Text(
            o.paymentStatus.isEmpty
                ? o.paymentLabel
                : '${o.paymentLabel}  •  ${o.paymentStatus}',
            style: const TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              color: C.muted,
            ),
          ),
        ],
      ),
    );
  }

  /*
   * How the UPI payment stands. No button to enter a transaction ID: the
   * reference is given in the popup before the order is placed, so this is a
   * status card, not an action.
   */
  Widget _upi(Order o) {
    final store = app.settings;
    final qr = mediaUrl(store.upiQrUrl);
    final waiting = o.needsUpiReference;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardBox(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const CircleAvatar(
                radius: 18,
                backgroundColor: C.brandSoft,
                child: Icon(Icons.qr_code_2_rounded, color: C.brand, size: 20),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Pay by UPI',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: C.ink,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: waiting ? C.amberSoft : C.brandSoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  o.paymentStatus.isEmpty ? 'Payment' : o.paymentStatus,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                    color: waiting ? C.amber : C.brandDark,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            waiting
                ? 'We have your reference. The store verifies it against the '
                    'bank statement, usually within a few minutes.'
                : 'Payment received for this order.',
            style: const TextStyle(
              fontSize: 12,
              height: 1.4,
              fontWeight: FontWeight.w600,
              color: C.muted,
            ),
          ),
          if (qr.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(5),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: C.line),
                  ),
                  child: Image.network(
                    qr,
                    width: 86,
                    height: 86,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const SizedBox(
                      width: 86,
                      height: 86,
                      child: Icon(Icons.qr_code_2_rounded,
                          size: 40, color: C.muted),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'UPI ID',
                        style: TextStyle(
                          fontSize: 10,
                          letterSpacing: 0.5,
                          fontWeight: FontWeight.w900,
                          color: C.muted,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF1F5F9),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          store.upiId,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w800,
                            color: C.ink,
                          ),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Note: ${o.number}',
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: C.muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _delivery(Order o) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: cardBox(),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CircleAvatar(
            radius: 20,
            backgroundColor: C.brandSoft,
            child: Icon(Icons.location_on_rounded, color: C.brand),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Delivering to',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: C.muted,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  o.recipient.isEmpty ? 'Your address' : o.recipient,
                  style: const TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w900,
                    color: C.ink,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  [o.address, o.recipientMobile]
                      .where((e) => e.isNotEmpty)
                      .join('\n'),
                  style: const TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    fontWeight: FontWeight.w500,
                    color: C.body,
                  ),
                ),
                if (o.notes.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Note: ${o.notes}',
                    style: const TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: C.muted,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
