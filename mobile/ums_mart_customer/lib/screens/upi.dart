// The UPI step, as one bottom sheet - the same shape as the website popup.
//
// Order on screen is the order the customer pays in:
//   1. the store QR code, the amount, the UPI ID (with copy) and the note
//   2. Transaction ID / UTR      - required
//   3. PhonePe / Google Pay number - optional
//
// It is used twice:
//   * from checkout, before the order exists: the values are collected here and
//     handed back to the checkout screen;
//   * as a blocking gate for an order that still has no reference, where there
//     is no way out except saving it.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../ui.dart';

class UpiReference {
  const UpiReference({required this.reference, this.mobile = ''});

  final String reference;
  final String mobile;
}

const int _minReference = 6;

/// Opens the UPI sheet. Returns null when the customer backs out.
Future<UpiReference?> showUpiSheet(
  BuildContext context, {
  required String upiId,
  required String payeeName,
  required String qrUrl,
  required double amount,
  String note = '',
  UpiReference? initial,
  bool blocking = false,
  String buttonLabel = 'Continue to place order',
  String? error,
}) {
  return showModalBottomSheet<UpiReference>(
    context: context,
    isScrollControlled: true,
    isDismissible: !blocking,
    enableDrag: !blocking,
    backgroundColor: Colors.white,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (ctx) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
      child: _UpiSheet(
        upiId: upiId,
        payeeName: payeeName,
        qrUrl: qrUrl,
        amount: amount,
        note: note,
        initial: initial,
        blocking: blocking,
        buttonLabel: buttonLabel,
        error: error,
      ),
    ),
  );
}

class _UpiSheet extends StatefulWidget {
  const _UpiSheet({
    required this.upiId,
    required this.payeeName,
    required this.qrUrl,
    required this.amount,
    required this.note,
    required this.initial,
    required this.blocking,
    required this.buttonLabel,
    required this.error,
  });

  final String upiId;
  final String payeeName;
  final String qrUrl;
  final double amount;
  final String note;
  final UpiReference? initial;
  final bool blocking;
  final String buttonLabel;
  final String? error;

  @override
  State<_UpiSheet> createState() => _UpiSheetState();
}

class _UpiSheetState extends State<_UpiSheet> {
  late final TextEditingController _ref =
      TextEditingController(text: widget.initial?.reference ?? '');
  late final TextEditingController _mobile =
      TextEditingController(text: widget.initial?.mobile ?? '');

  @override
  void initState() {
    super.initState();
    _ref.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _ref.dispose();
    _mobile.dispose();
    super.dispose();
  }

  String get _clean => _ref.text.trim().replaceAll(RegExp(r'\s+'), '');
  bool get _ok => _clean.length >= _minReference;

  Future<void> _copy() async {
    await Clipboard.setData(ClipboardData(text: widget.upiId));
    if (mounted) toast(context, 'UPI ID copied');
  }

  void _submit() {
    if (!_ok) {
      toast(context, 'Enter the transaction ID / UTR to continue');
      return;
    }
    Navigator.of(context).pop(
      UpiReference(reference: _clean, mobile: _mobile.text.trim()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final qr = mediaUrl(widget.qrUrl);
    return SafeArea(
      top: false,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(18, 10, 18, 18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 42,
                height: 4,
                margin: const EdgeInsets.only(bottom: 14),
                decoration: BoxDecoration(
                  color: C.line,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Pay by UPI',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                      color: C.ink,
                    ),
                  ),
                ),
                if (!widget.blocking)
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close_rounded, color: C.muted),
                    tooltip: 'Close',
                  ),
              ],
            ),

            // ---- 1. the QR + UPI ID ------------------------------------
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: C.brandSoft.withValues(alpha: 0.35),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: C.line),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: C.line),
                    ),
                    child: qr.isEmpty
                        ? const SizedBox(
                            width: 118,
                            height: 118,
                            child: Icon(Icons.qr_code_2_rounded,
                                size: 60, color: C.muted),
                          )
                        : Image.network(
                            qr,
                            width: 118,
                            height: 118,
                            fit: BoxFit.contain,
                            errorBuilder: (_, __, ___) => const SizedBox(
                              width: 118,
                              height: 118,
                              child: Icon(Icons.qr_code_2_rounded,
                                  size: 60, color: C.muted),
                            ),
                          ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'PAY THIS AMOUNT',
                          style: TextStyle(
                            fontSize: 10,
                            letterSpacing: 0.6,
                            fontWeight: FontWeight.w900,
                            color: C.muted,
                          ),
                        ),
                        Text(
                          money(widget.amount),
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w900,
                            color: C.ink,
                          ),
                        ),
                        if (widget.payeeName.isNotEmpty)
                          Text(
                            'to ${widget.payeeName}',
                            style: const TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w600,
                              color: C.muted,
                            ),
                          ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Flexible(
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: C.line),
                                ),
                                child: Text(
                                  widget.upiId,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w800,
                                    color: C.ink,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            GestureDetector(
                              onTap: _copy,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 5),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: C.line),
                                ),
                                child: const Text(
                                  'Copy',
                                  style: TextStyle(
                                    fontSize: 10.5,
                                    fontWeight: FontWeight.w900,
                                    color: C.brandDark,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        if (widget.note.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            widget.note,
                            style: const TextStyle(
                              fontSize: 10.5,
                              height: 1.3,
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
            ),
            const SizedBox(height: 6),
            const Text(
              'Scan with GPay, PhonePe, Paytm or your bank app.',
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w600,
                color: C.muted,
              ),
            ),

            // ---- 2. transaction id -------------------------------------
            const SizedBox(height: 14),
            const Text(
              'Transaction ID / UTR *',
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: C.ink,
              ),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _ref,
              keyboardType: TextInputType.number,
              textInputAction: TextInputAction.next,
              maxLength: 40,
              decoration: const InputDecoration(
                hintText: 'e.g. 4291000111222333',
                counterText: '',
              ),
            ),

            // ---- 3. optional phone -------------------------------------
            const SizedBox(height: 12),
            const Text(
              'PhonePe / Google Pay number (optional)',
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: C.ink,
              ),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _mobile,
              keyboardType: TextInputType.text,
              maxLength: 30,
              decoration: const InputDecoration(
                hintText: 'Optional — 9876543210 or 9876543210@ybl',
                counterText: '',
              ),
            ),

            const SizedBox(height: 4),
            const Text(
              'The transaction ID is under “Payment history” in your UPI app '
              '(“UTR” in some banks).',
              style: TextStyle(
                fontSize: 10.5,
                height: 1.35,
                fontWeight: FontWeight.w600,
                color: C.muted,
              ),
            ),

            if (widget.error != null) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: C.roseSoft,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  widget.error!,
                  style: const TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                    color: C.rose,
                  ),
                ),
              ),
            ],

            if (!_ok) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: C.brandSoft,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  widget.blocking
                      ? 'Enter the transaction ID to continue to your order.'
                      : 'Enter the transaction ID to place your order.',
                  style: const TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                    color: C.brandDark,
                  ),
                ),
              ),
            ],

            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _ok ? _submit : null,
                child: Text(widget.buttonLabel),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
