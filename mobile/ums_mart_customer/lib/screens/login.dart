// Sign in with a mobile number and a 6-digit code. No password.
// Closes with `true` when the shopper is signed in.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../store.dart';
import '../ui.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _mobile = TextEditingController();
  final TextEditingController _code = TextEditingController();
  final FocusNode _codeFocus = FocusNode();
  Timer? _timer;
  bool _codeStep = false;
  bool _busy = false;
  String? _error;
  String _devCode = '';
  int _wait = 0;

  @override
  void dispose() {
    _timer?.cancel();
    _mobile.dispose();
    _code.dispose();
    _codeFocus.dispose();
    super.dispose();
  }

  String get _number => '+91${_mobile.text.trim()}';

  void _startWait(int seconds) {
    _timer?.cancel();
    setState(() => _wait = seconds <= 0 ? 30 : seconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      setState(() => _wait -= 1);
      if (_wait <= 0) timer.cancel();
    });
  }

  int _seconds(dynamic value) {
    if (value is num) return value.toInt();
    return int.tryParse('$value') ?? 30;
  }

  Future<void> _sendCode({bool again = false}) async {
    if (_busy) return;
    if (_mobile.text.trim().length != 10) {
      setState(() => _error = 'Enter your 10-digit mobile number.');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final reply =
          again ? await Api.resendOtp(_number) : await Api.sendOtp(_number);
      if (!mounted) return;
      setState(() {
        _codeStep = true;
        _busy = false;
        _devCode = '${reply['dev_otp'] ?? ''}';
        _code.clear();
      });
      _startWait(_seconds(reply['resend_cooldown_seconds']));
      // Put the cursor in the code box so the shopper can type at once.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _codeStep) _codeFocus.requestFocus();
      });
      if (again) toast(context, 'A new code was sent');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = errorText(e);
      });
    }
  }

  Future<void> _verify() async {
    if (_busy) return;
    final code = _code.text.trim();
    if (code.length < 4) {
      setState(() => _error = 'Enter the code we sent you.');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await app.verifyOtp(_number, code);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      // Any problem is shown here; nothing is allowed to close the app.
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = errorText(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () {
            if (_codeStep && !_busy) {
              setState(() {
                _codeStep = false;
                _error = null;
              });
            } else {
              Navigator.of(context).pop(false);
            }
          },
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Container(
                height: 76,
                width: 76,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: C.brandGradient,
                  borderRadius: BorderRadius.circular(22),
                ),
                child: Icon(
                  _codeStep
                      ? Icons.lock_open_rounded
                      : Icons.phone_iphone_rounded,
                  color: Colors.white,
                  size: 38,
                ),
              ),
            ),
            const SizedBox(height: 22),
            Text(
              _codeStep ? 'Enter the code' : 'Welcome to UMS Mart',
              style: const TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w900,
                color: C.ink,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              _codeStep
                  ? 'We sent a 6-digit code to $_number'
                  : 'Sign in with your mobile number. No password needed.',
              style: const TextStyle(
                fontSize: 14,
                height: 1.4,
                fontWeight: FontWeight.w500,
                color: C.muted,
              ),
            ),
            const SizedBox(height: 26),
            if (!_codeStep) ...[
              TextField(
                controller: _mobile,
                autofocus: true,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.done,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(10),
                ],
                onSubmitted: (_) => _sendCode(),
                style: const TextStyle(
                  fontSize: 18,
                  letterSpacing: 1,
                  fontWeight: FontWeight.w800,
                  color: C.ink,
                ),
                decoration: const InputDecoration(
                  labelText: 'Mobile number',
                  prefixIcon: Padding(
                    padding: EdgeInsets.fromLTRB(16, 14, 8, 14),
                    child: Text(
                      '+91',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: C.ink,
                      ),
                    ),
                  ),
                  hintText: '98765 00001',
                ),
              ),
            ] else ...[
              TextField(
                controller: _code,
                focusNode: _codeFocus,
                keyboardType: TextInputType.number,
                textAlign: TextAlign.center,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(6),
                ],
                onSubmitted: (_) => _verify(),
                style: const TextStyle(
                  fontSize: 26,
                  letterSpacing: 10,
                  fontWeight: FontWeight.w900,
                  color: C.ink,
                ),
                decoration: const InputDecoration(hintText: '------'),
              ),
              if (_devCode.isNotEmpty) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.only(left: 14),
                  decoration: BoxDecoration(
                    color: C.brandSoft,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.developer_mode_rounded,
                          size: 18, color: C.brand),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Test code: $_devCode',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                            color: C.brandDark,
                          ),
                        ),
                      ),
                      TextButton(
                        onPressed: () => setState(() => _code.text = _devCode),
                        child: const Text('Use'),
                      ),
                    ],
                  ),
                ),
              ],
            ],
            if (_error != null) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: C.roseSoft,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  _error!,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: C.rose,
                  ),
                ),
              ),
            ],
            const SizedBox(height: 20),
            BusyButton(
              label: _codeStep ? 'Verify and continue' : 'Send code',
              busy: _busy,
              onPressed: _codeStep ? _verify : _sendCode,
            ),
            if (_codeStep) ...[
              const SizedBox(height: 8),
              Center(
                child: TextButton(
                  onPressed: _wait > 0 || _busy
                      ? null
                      : () => _sendCode(again: true),
                  child: Text(
                      _wait > 0 ? 'Send again in ${_wait}s' : 'Send code again'),
                ),
              ),
            ],
            const SizedBox(height: 18),
            const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.shopping_cart_outlined, size: 15, color: C.muted),
                SizedBox(width: 6),
                Text(
                  'Your cart is kept when you sign in',
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: C.muted,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
