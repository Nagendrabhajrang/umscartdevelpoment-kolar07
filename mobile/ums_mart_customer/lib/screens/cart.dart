// Cart tab: items with quantity and delete, coupon, bill, checkout button.

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../store.dart';
import '../ui.dart';
import 'checkout.dart';

class CartTab extends StatefulWidget {
  const CartTab({super.key});

  @override
  State<CartTab> createState() => _CartTabState();
}

class _CartTabState extends State<CartTab> {
  final TextEditingController _coupon = TextEditingController();
  final Set<int> _busy = <int>{};
  bool _couponBusy = false;

  @override
  void initState() {
    super.initState();
    app.tab.addListener(_tabChanged);
  }

  @override
  void dispose() {
    app.tab.removeListener(_tabChanged);
    _coupon.dispose();
    super.dispose();
  }

  void _tabChanged() {
    if (app.tab.value == 2) app.refreshCart();
  }

  /// Runs one change on a line. The line is dimmed while it runs, and any
  /// problem is shown, so a tap is never silent.
  Future<void> _change(CartLine line, Future<void> Function() action,
      {String? done}) async {
    if (_busy.contains(line.id)) return;
    setState(() => _busy.add(line.id));
    try {
      await action();
      if (mounted && done != null) toast(context, done);
    } catch (e) {
      if (mounted) toast(context, errorText(e));
    } finally {
      if (mounted) setState(() => _busy.remove(line.id));
    }
  }

  Future<void> _applyCoupon() async {
    final code = _coupon.text.trim();
    if (code.isEmpty || _couponBusy) return;
    FocusScope.of(context).unfocus();
    setState(() => _couponBusy = true);
    try {
      await app.applyCoupon(code);
      _coupon.clear();
      if (mounted) toast(context, 'Coupon applied');
    } catch (e) {
      if (mounted) toast(context, errorText(e));
    } finally {
      if (mounted) setState(() => _couponBusy = false);
    }
  }

  Future<void> _removeCoupon() async {
    if (_couponBusy) return;
    setState(() => _couponBusy = true);
    try {
      await app.removeCoupon();
      if (mounted) toast(context, 'Coupon removed');
    } catch (e) {
      if (mounted) toast(context, errorText(e));
    } finally {
      if (mounted) setState(() => _couponBusy = false);
    }
  }

  Future<void> _checkout() async {
    final ok = await requireLogin(context);
    if (!ok || !mounted) return;
    if (app.cart.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const CheckoutScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final cart = app.cart;
        final bill = app.bill;
        final count = cart.count;
        return Scaffold(
          appBar: AppBar(
            title: Text(count == 0
                ? 'My cart'
                : 'My cart  ($count ${count == 1 ? 'item' : 'items'})'),
          ),
          body: cart.isEmpty
              ? Notice(
                  icon: Icons.shopping_cart_outlined,
                  title: 'Your cart is empty',
                  text: 'Add fresh groceries and they will show up here.',
                  button: 'Start shopping',
                  onButton: () => app.tab.value = 0,
                )
              : RefreshIndicator(
                  color: C.brand,
                  onRefresh: app.refreshCart,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                    children: [
                      _eta(),
                      const SizedBox(height: 14),
                      Container(
                        decoration: cardBox(),
                        child: Column(
                          children: [
                            for (var i = 0; i < cart.lines.length; i++) ...[
                              if (i > 0)
                                const Divider(indent: 14, endIndent: 14),
                              _line(cart.lines[i]),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      _couponBox(cart, bill),
                      if (bill != null) ...[
                        const SizedBox(height: 14),
                        if (bill.toFreeDelivery > 0 && bill.delivery > 0)
                          _hint(
                            Icons.local_shipping_outlined,
                            'Add ${money(bill.toFreeDelivery)} more for free delivery',
                            C.blue,
                            const Color(0xFFEAF1FF),
                          ),
                        if (!bill.minimumMet)
                          _hint(
                            Icons.info_outline_rounded,
                            'Minimum order is ${money(bill.minimumOrder)}. Add a few more items.',
                            const Color(0xFFB45309),
                            C.amberSoft,
                          ),
                        BillCard(bill: bill),
                      ],
                    ],
                  ),
                ),
          bottomNavigationBar: cart.isEmpty
              ? null
              : Container(
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    border: Border(top: BorderSide(color: C.line)),
                  ),
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
                  child: Row(
                    children: [
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            money(bill?.total ?? cart.subtotal),
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w900,
                              color: C.ink,
                            ),
                          ),
                          const Text(
                            'Total to pay',
                            style: TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w600,
                              color: C.muted,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: FilledButton(
                          onPressed: (bill != null && !bill.minimumMet)
                              ? null
                              : _checkout,
                          child: Text(app.signedIn
                              ? 'Proceed to checkout'
                              : 'Sign in to checkout'),
                        ),
                      ),
                    ],
                  ),
                ),
        );
      },
    );
  }

  Widget _eta() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        gradient: C.brandGradient,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.bolt_rounded, color: Color(0xFFFFE08A)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Arriving in about ${app.settings.etaMinutes} minutes',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13.5,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _hint(IconData icon, String text, Color color, Color background) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Icon(icon, size: 19, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _line(CartLine line) {
    final busy = _busy.contains(line.id);
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 150),
      opacity: busy ? 0.45 : 1,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 6, 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              height: 66,
              width: 66,
              child: NetImage(line.image, label: line.name, radius: 14),
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
                      height: 1.25,
                      fontWeight: FontWeight.w800,
                      color: C.ink,
                    ),
                  ),
                  if (line.unit.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        line.unit,
                        style: const TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: C.muted,
                        ),
                      ),
                    ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Text(
                        money(line.total),
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w900,
                          color: C.ink,
                        ),
                      ),
                      if (!line.available) ...[
                        const SizedBox(width: 8),
                        const Text(
                          'Not available',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            color: C.rose,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                // Delete: a full-size button so it is easy to hit.
                IconButton(
                  tooltip: 'Remove item',
                  onPressed: busy
                      ? null
                      : () => _change(
                            line,
                            () => app.removeLine(line),
                            done: 'Item removed from cart',
                          ),
                  icon: const Icon(Icons.delete_outline_rounded),
                  color: C.rose,
                  iconSize: 22,
                ),
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: Container(
                    decoration: BoxDecoration(
                      color: C.brand,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _step(
                          Icons.remove_rounded,
                          busy
                              ? null
                              : () => _change(
                                    line,
                                    () => app.setQuantity(
                                        line, line.quantity - 1),
                                  ),
                        ),
                        SizedBox(
                          width: 24,
                          child: Text(
                            '${line.quantity}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13.5,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        _step(
                          Icons.add_rounded,
                          busy
                              ? null
                              : () => _change(
                                    line,
                                    () => app.setQuantity(
                                        line, line.quantity + 1),
                                  ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _step(IconData icon, VoidCallback? onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        height: 34,
        width: 34,
        child: Icon(icon, size: 18, color: Colors.white),
      ),
    );
  }

  Widget _couponBox(Cart cart, Bill? bill) {
    final applied = cart.coupon.isNotEmpty
        ? cart.coupon
        : (bill != null ? bill.coupon : '');
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: cardBox(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.local_offer_rounded, size: 18, color: C.amber),
              SizedBox(width: 8),
              Text(
                'Coupon',
                style: TextStyle(
                  fontSize: 14.5,
                  fontWeight: FontWeight.w900,
                  color: C.ink,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (applied.isNotEmpty)
            Container(
              padding: const EdgeInsets.only(left: 12),
              decoration: BoxDecoration(
                color: C.brandSoft,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_rounded,
                      size: 18, color: C.brand),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '$applied applied',
                      style: const TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w800,
                        color: C.brandDark,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: _couponBusy ? null : _removeCoupon,
                    style: TextButton.styleFrom(foregroundColor: C.rose),
                    child: const Text('Remove'),
                  ),
                ],
              ),
            )
          else
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _coupon,
                    textCapitalization: TextCapitalization.characters,
                    onSubmitted: (_) => _applyCoupon(),
                    decoration: const InputDecoration(
                      hintText: 'Enter coupon code',
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                FilledButton(
                  onPressed: _couponBusy ? null : _applyCoupon,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(84, 48),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                  child: const Text('Apply'),
                ),
              ],
            ),
        ],
      ),
    );
  }
}
