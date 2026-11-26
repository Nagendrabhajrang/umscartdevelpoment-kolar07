// Checkout: pick an address, confirm the bill, place the order.
// Also the "add address" form, used here and in the profile.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../models.dart';
import '../store.dart';
import '../ui.dart';
import 'orders.dart';
import 'upi.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final TextEditingController _notes = TextEditingController();
  List<Address> _addresses = const [];
  int? _selected;
  Bill? _bill;
  bool _loading = true;
  bool _placing = false;
  String? _error;

  /*
   * Payment method, and - when UPI is chosen - the reference the customer typed
   * into the popup. The QR is never drawn on this screen: choosing UPI opens the
   * popup, and a UPI order is not created until a transaction ID is in hand.
   */
  String _method = 'cod';
  UpiReference? _upiRef;

  @override
  void initState() {
    super.initState();
    _bill = app.bill;
    if (!app.settings.codEnabled) _method = 'upi';
    _load();
  }

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final list = await Api.addresses();
      if (!mounted) return;
      int? pick = _selected;
      if (pick == null || !list.any((a) => a.id == pick)) {
        if (list.isEmpty) {
          pick = null;
        } else {
          pick = list
              .firstWhere((a) => a.isDefault, orElse: () => list.first)
              .id;
        }
      }
      setState(() {
        _addresses = list;
        _selected = pick;
        _loading = false;
      });
      _preview();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = errorText(e);
        _loading = false;
      });
    }
  }

  Future<void> _preview() async {
    final id = _selected;
    if (id == null) return;
    try {
      final bill =
          await Api.checkoutPreview(addressId: id, paymentMethod: _method);
      if (mounted && _selected == id) setState(() => _bill = bill);
    } catch (_) {
      // The cart's own bill stays on screen.
    }
  }

  Future<void> _addAddress() async {
    final added = await showAddressForm(context);
    if (added == null || !mounted) return;
    _selected = added.id;
    await _load();
  }

  /// Opens the UPI popup and keeps what the customer typed.
  Future<void> _collectUpi() async {
    final store = app.settings;
    final got = await showUpiSheet(
      context,
      upiId: store.upiId,
      payeeName: store.upiPayeeName,
      qrUrl: store.upiQrUrl,
      amount: _bill?.total ?? 0,
      note: 'Use your order number as the payment note.',
      initial: _upiRef,
    );
    if (got != null && mounted) setState(() => _upiRef = got);
  }

  /// Sends the reference to the payment that now exists. If it fails the popup
  /// comes back as a blocking step - the order exists, so it must not be left
  /// looking paid without one.
  Future<void> _saveProof(Order order) async {
    final paymentId = order.paymentId;
    var ref = _upiRef;
    if (paymentId == null || ref == null) return;
    var error = '';
    while (true) {
      try {
        await Api.submitUpiProof(
          paymentId,
          reference: ref!.reference,
          payerMobile: ref.mobile,
        );
        return;
      } catch (e) {
        error = errorText(e);
        if (!mounted) return;
        final store = app.settings;
        final again = await showUpiSheet(
          context,
          upiId: store.upiId,
          payeeName: store.upiPayeeName,
          qrUrl: store.upiQrUrl,
          amount: order.total,
          note: 'Payment note: ${order.number}',
          initial: ref,
          blocking: true,
          buttonLabel: 'Save & view my order',
          error: error,
        );
        if (again == null) return;
        ref = again;
        _upiRef = again;
      }
    }
  }

  Future<void> _place() async {
    final id = _selected;
    if (id == null) {
      toast(context, 'Please add a delivery address');
      return;
    }
    /*
     * No reference, no order: a UPI order the store cannot match to a payment is
     * exactly the order that gets abandoned. The popup is the way forward.
     */
    if (_method == 'upi' && _upiRef == null) {
      await _collectUpi();
      return;
    }

    setState(() => _placing = true);
    try {
      final order = await Api.checkout(
        addressId: id,
        notes: _notes.text.trim(),
        paymentMethod: _method,
      );
      if (order.isUpi) await _saveProof(order);
      await app.refreshCart();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => OrderPlacedScreen(order: order)),
      );
    } catch (e) {
      if (mounted) {
        setState(() => _placing = false);
        toast(context, errorText(e));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final bill = _bill;
    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: _loading
          ? const Loading()
          : _error != null
              ? Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not open checkout',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                )
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                  children: [
                    _heading('1', 'Delivery address'),
                    Container(
                      decoration: cardBox(),
                      child: Column(
                        children: [
                          for (final a in _addresses) ...[
                            InkWell(
                              onTap: () {
                                setState(() => _selected = a.id);
                                _preview();
                              },
                              child: Padding(
                                padding: const EdgeInsets.all(14),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Icon(
                                      _selected == a.id
                                          ? Icons.radio_button_checked_rounded
                                          : Icons.radio_button_off_rounded,
                                      color: _selected == a.id
                                          ? C.brand
                                          : C.muted,
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(child: AddressText(address: a)),
                                  ],
                                ),
                              ),
                            ),
                            const Divider(),
                          ],
                          InkWell(
                            onTap: _addAddress,
                            child: const Padding(
                              padding: EdgeInsets.all(14),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.add_location_alt_outlined,
                                      color: C.brand, size: 20),
                                  SizedBox(width: 8),
                                  Text(
                                    'Add a new address',
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w800,
                                      color: C.brand,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    _heading('2', 'Payment'),
                    if (app.settings.codEnabled)
                      _payTile(
                        selected: _method == 'cod',
                        icon: Icons.payments_rounded,
                        title: 'Cash on delivery',
                        subtitle: bill == null
                            ? 'Pay when your order arrives'
                            : 'Pay ${money(bill.total)} when your order arrives',
                        onTap: () => setState(() => _method = 'cod'),
                      ),
                    if (app.settings.canPayByUpi) ...[
                      const SizedBox(height: 10),
                      _payTile(
                        selected: _method == 'upi',
                        icon: Icons.qr_code_2_rounded,
                        title: 'UPI — pay now',
                        subtitle: app.settings.upiId,
                        onTap: () async {
                          setState(() => _method = 'upi');
                          if (_upiRef == null) await _collectUpi();
                        },
                      ),
                      /*
                       * No QR here - it lives in the popup. This is only the
                       * receipt line, with one way back into the popup.
                       */
                      if (_method == 'upi')
                        Container(
                          margin: const EdgeInsets.only(top: 10),
                          padding: const EdgeInsets.fromLTRB(14, 10, 10, 10),
                          decoration: BoxDecoration(
                            color: C.brandSoft,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: C.line),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _upiRef == null
                                          ? 'UPI REFERENCE NEEDED'
                                          : 'UPI REFERENCE RECORDED',
                                      style: const TextStyle(
                                        fontSize: 9.5,
                                        letterSpacing: 0.5,
                                        fontWeight: FontWeight.w900,
                                        color: C.brandDark,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      _upiRef == null
                                          ? 'Pay with any UPI app, then enter the transaction ID.'
                                          : '${_upiRef!.reference}${_upiRef!.mobile.isEmpty ? '' : ' · ${_upiRef!.mobile}'}',
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.w700,
                                        color: C.ink,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              TextButton(
                                onPressed: _collectUpi,
                                child: Text(_upiRef == null ? 'Enter ID' : 'Change'),
                              ),
                            ],
                          ),
                        ),
                    ],
                    _heading('3', 'Note for the delivery person'),
                    TextField(
                      controller: _notes,
                      maxLines: 2,
                      maxLength: 200,
                      decoration: const InputDecoration(
                        hintText: 'Optional, for example: call when you arrive',
                        counterText: '',
                      ),
                    ),
                    if (bill != null) ...[
                      const SizedBox(height: 18),
                      for (final issue in bill.issues)
                        Container(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: C.roseSoft,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            issue,
                            style: const TextStyle(
                              fontSize: 12.5,
                              fontWeight: FontWeight.w700,
                              color: C.rose,
                            ),
                          ),
                        ),
                      BillCard(bill: bill),
                    ],
                  ],
                ),
      bottomNavigationBar: _loading || _error != null
          ? null
          : Container(
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(top: BorderSide(color: C.line)),
              ),
              child: SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
                  child: BusyButton(
                    label: bill == null
                        ? 'Place order'
                        : 'Place order  •  ${money(bill.total)}',
                    busy: _placing,
                    onPressed: _place,
                  ),
                ),
              ),
            ),
    );
  }

  Widget _payTile({
    required bool selected,
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: selected ? C.brand : C.line,
            width: selected ? 1.4 : 1,
          ),
        ),
        child: Row(
          children: [
            CircleAvatar(
              radius: 21,
              backgroundColor: selected ? C.brandSoft : const Color(0xFFF3F4F6),
              child: Icon(icon, color: selected ? C.brand : C.muted),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w800,
                      color: C.ink,
                    ),
                  ),
                  if (subtitle.isNotEmpty)
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: C.muted,
                      ),
                    ),
                ],
              ),
            ),
            Icon(
              selected
                  ? Icons.radio_button_checked_rounded
                  : Icons.radio_button_off_rounded,
              color: selected ? C.brand : C.muted,
            ),
          ],
        ),
      ),
    );
  }

  Widget _heading(String number, String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 18, 0, 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 11,
            backgroundColor: C.brand,
            child: Text(
              number,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 9),
          Text(
            title,
            style: const TextStyle(
              fontSize: 15.5,
              fontWeight: FontWeight.w900,
              color: C.ink,
            ),
          ),
        ],
      ),
    );
  }
}

/// Label, name and full address in three lines.
class AddressText extends StatelessWidget {
  const AddressText({super.key, required this.address});

  final Address address;

  @override
  Widget build(BuildContext context) {
    final a = address;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Flexible(
              child: Text(
                a.recipient.isEmpty ? a.label : '${a.label}  •  ${a.recipient}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: C.ink,
                ),
              ),
            ),
            if (a.isDefault) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: C.brandSoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'DEFAULT',
                  style: TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w900,
                    color: C.brandDark,
                  ),
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 3),
        Text(
          a.full,
          style: const TextStyle(
            fontSize: 12.5,
            height: 1.35,
            fontWeight: FontWeight.w500,
            color: C.muted,
          ),
        ),
        if (a.mobile.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              a.mobile,
              style: const TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: C.muted,
              ),
            ),
          ),
      ],
    );
  }
}

// ------------------------------------------------------------ address form

/// Opens the address form. Returns the saved address, or null if closed.
Future<Address?> showAddressForm(BuildContext context) {
  return showModalBottomSheet<Address>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.white,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (_) => const _AddressForm(),
  );
}

class _AddressForm extends StatefulWidget {
  const _AddressForm();

  @override
  State<_AddressForm> createState() => _AddressFormState();
}

class _AddressFormState extends State<_AddressForm> {
  final GlobalKey<FormState> _form = GlobalKey<FormState>();
  late final TextEditingController _name =
      TextEditingController(text: app.account?.name ?? '');
  late final TextEditingController _mobile = TextEditingController(
      text: (app.account?.mobile ?? '').replaceFirst('+91', ''));
  final TextEditingController _line1 = TextEditingController();
  final TextEditingController _line2 = TextEditingController();
  final TextEditingController _landmark = TextEditingController();
  final TextEditingController _city = TextEditingController();
  final TextEditingController _state = TextEditingController();
  final TextEditingController _pincode = TextEditingController();
  String _label = 'home';
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    for (final c in [
      _name, _mobile, _line1, _line2, _landmark, _city, _state, _pincode,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _need(String? value, String message, {int min = 1}) =>
      (value ?? '').trim().length < min ? message : null;

  Future<void> _save() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final address = await Api.addAddress(<String, dynamic>{
        'label': _label,
        'recipient_name': _name.text.trim(),
        'recipient_mobile': '+91${_mobile.text.trim()}',
        'line1': _line1.text.trim(),
        'line2': _line2.text.trim(),
        'landmark': _landmark.text.trim(),
        'city': _city.text.trim(),
        'state': _state.text.trim(),
        'pincode': _pincode.text.trim(),
        'is_default': true,
      });
      if (mounted) Navigator.of(context).pop(address);
    } catch (e) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = errorText(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    const gap = SizedBox(height: 12);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 20),
          child: Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Center(
                  child: Container(
                    height: 4,
                    width: 44,
                    decoration: BoxDecoration(
                      color: C.line,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'New delivery address',
                  style: TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w900,
                    color: C.ink,
                  ),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    for (final entry in const {
                      'home': 'Home',
                      'work': 'Work',
                      'other': 'Other',
                    }.entries)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(entry.value),
                          selected: _label == entry.key,
                          showCheckmark: false,
                          selectedColor: C.brand,
                          backgroundColor: Colors.white,
                          side: BorderSide(
                            color: _label == entry.key ? C.brand : C.line,
                          ),
                          labelStyle: TextStyle(
                            fontWeight: FontWeight.w800,
                            color:
                                _label == entry.key ? Colors.white : C.body,
                          ),
                          onSelected: (_) => setState(() => _label = entry.key),
                        ),
                      ),
                  ],
                ),
                gap,
                TextFormField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Full name'),
                  validator: (v) => _need(v, 'Enter the name', min: 2),
                ),
                gap,
                TextFormField(
                  controller: _mobile,
                  keyboardType: TextInputType.phone,
                  inputFormatters: [
                    FilteringTextInputFormatter.digitsOnly,
                    LengthLimitingTextInputFormatter(10),
                  ],
                  decoration: const InputDecoration(
                    labelText: 'Mobile number',
                    prefixText: '+91  ',
                  ),
                  validator: (v) => (v ?? '').trim().length == 10
                      ? null
                      : 'Enter a 10-digit mobile number',
                ),
                gap,
                TextFormField(
                  controller: _line1,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(
                      labelText: 'House / flat number, building'),
                  validator: (v) => _need(v, 'Enter the house or flat', min: 3),
                ),
                gap,
                TextFormField(
                  controller: _line2,
                  textCapitalization: TextCapitalization.words,
                  decoration:
                      const InputDecoration(labelText: 'Street, area (optional)'),
                ),
                gap,
                TextFormField(
                  controller: _landmark,
                  textCapitalization: TextCapitalization.words,
                  decoration:
                      const InputDecoration(labelText: 'Landmark (optional)'),
                ),
                gap,
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _city,
                        textCapitalization: TextCapitalization.words,
                        decoration: const InputDecoration(labelText: 'City'),
                        validator: (v) => _need(v, 'Enter the city', min: 2),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _pincode,
                        keyboardType: TextInputType.number,
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(6),
                        ],
                        decoration: const InputDecoration(labelText: 'Pincode'),
                        validator: (v) => (v ?? '').trim().length == 6
                            ? null
                            : '6-digit pincode',
                      ),
                    ),
                  ],
                ),
                gap,
                TextFormField(
                  controller: _state,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'State'),
                  validator: (v) => _need(v, 'Enter the state', min: 2),
                ),
                if (_error != null) ...[
                  gap,
                  Text(
                    _error!,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: C.rose,
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                BusyButton(
                  label: 'Save address',
                  busy: _saving,
                  onPressed: _save,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ------------------------------------------------------------ order placed

class OrderPlacedScreen extends StatelessWidget {
  const OrderPlacedScreen({super.key, required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            children: [
              const Spacer(),
              Container(
                height: 110,
                width: 110,
                decoration: const BoxDecoration(
                  gradient: C.brandGradient,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_rounded,
                    size: 64, color: Colors.white),
              ),
              const SizedBox(height: 24),
              const Text(
                'Order placed!',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                  color: C.ink,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Order ${order.number}',
                style: const TextStyle(
                  fontSize: 14.5,
                  fontWeight: FontWeight.w800,
                  color: C.brand,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'We are getting it ready. It will reach you in about '
                '${app.settings.etaMinutes} minutes.\n'
                '${order.isUpi ? 'Your UPI payment is with the store for verification.' : 'Pay ${money(order.total)} in cash on delivery.'}',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  height: 1.5,
                  fontWeight: FontWeight.w500,
                  color: C.muted,
                ),
              ),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () {
                    Navigator.of(context).pushReplacement(
                      MaterialPageRoute<void>(
                        builder: (_) => OrderScreen(orderId: order.id),
                      ),
                    );
                  },
                  child: const Text('Track my order'),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: () => openHome(context),
                  child: const Text('Continue shopping'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
