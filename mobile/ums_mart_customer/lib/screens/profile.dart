// Profile tab, plus the pages it opens: edit profile, addresses, wishlist.

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../store.dart';
import '../ui.dart';
import 'checkout.dart';

class ProfileTab extends StatelessWidget {
  const ProfileTab({super.key});

  Future<void> _signOut(BuildContext context) async {
    final sure = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        title: const Text(
          'Sign out?',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
        ),
        content: const Text('You can sign in again any time.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            style: TextButton.styleFrom(foregroundColor: C.muted),
            child: const Text('Stay'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: TextButton.styleFrom(foregroundColor: C.rose),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (sure != true) return;
    await app.signOut();
    if (context.mounted) toast(context, 'Signed out');
  }

  void _support(BuildContext context) {
    final s = app.settings;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      builder: (_) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 22, 22, 22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Help and support',
                style: TextStyle(
                    fontSize: 19, fontWeight: FontWeight.w900, color: C.ink),
              ),
              const SizedBox(height: 14),
              _SupportRow(Icons.call_rounded, 'Call us',
                  s.phone.isEmpty ? 'Not set yet' : s.phone),
              _SupportRow(Icons.mail_rounded, 'Email',
                  s.email.isEmpty ? 'Not set yet' : s.email),
              _SupportRow(Icons.store_rounded, 'Store',
                  s.address.isEmpty ? s.name : s.address),
            ],
          ),
        ),
      ),
    );
  }

  void _push(BuildContext context, Widget screen) {
    Navigator.of(context)
        .push(MaterialPageRoute<void>(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final account = app.account;
        return Scaffold(
          body: ListView(
            padding: EdgeInsets.zero,
            children: [
              _head(context, account),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                child: Column(
                  children: [
                    if (account != null) ...[
                      _Menu(children: [
                        _MenuRow(
                          icon: Icons.receipt_long_rounded,
                          title: 'My orders',
                          text: 'Track, view and cancel orders',
                          onTap: () => app.tab.value = 3,
                        ),
                        _MenuRow(
                          icon: Icons.location_on_rounded,
                          title: 'Saved addresses',
                          text: 'Where we deliver to',
                          onTap: () => _push(context, const AddressesScreen()),
                        ),
                        _MenuRow(
                          icon: Icons.favorite_rounded,
                          title: 'Wishlist',
                          text: 'Items you saved for later',
                          onTap: () => _push(context, const WishlistScreen()),
                        ),
                        _MenuRow(
                          icon: Icons.person_rounded,
                          title: 'Edit profile',
                          text: 'Name and email',
                          onTap: () => showEditProfile(context),
                        ),
                      ]),
                      const SizedBox(height: 14),
                    ],
                    _Menu(children: [
                      _MenuRow(
                        icon: Icons.shopping_cart_rounded,
                        title: 'My cart',
                        text: app.cart.count == 0
                            ? 'Your cart is empty'
                            : '${app.cart.count} in your cart',
                        onTap: () => app.tab.value = 2,
                      ),
                      _MenuRow(
                        icon: Icons.support_agent_rounded,
                        title: 'Help and support',
                        text: 'Call or email the store',
                        onTap: () => _support(context),
                      ),
                    ]),
                    if (account != null) ...[
                      const SizedBox(height: 14),
                      _Menu(children: [
                        _MenuRow(
                          icon: Icons.logout_rounded,
                          title: 'Sign out',
                          text: '',
                          color: C.rose,
                          onTap: () => _signOut(context),
                        ),
                      ]),
                    ],
                    const SizedBox(height: 22),
                    Text(
                      '${app.settings.name}  •  version 2.0',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: C.muted,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _head(BuildContext context, Account? account) {
    return Container(
      decoration: const BoxDecoration(
        gradient: C.brandGradient,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
          child: account == null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const CircleAvatar(
                      radius: 30,
                      backgroundColor: Colors.white,
                      child:
                          Icon(Icons.person_rounded, size: 34, color: C.brand),
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      'Hello there!',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Sign in to place orders, track deliveries and save addresses.',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 13.5,
                        height: 1.4,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: () => requireLogin(context),
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: C.brandDark,
                        minimumSize: const Size(double.infinity, 50),
                      ),
                      child: const Text('Sign in with mobile number'),
                    ),
                  ],
                )
              : Row(
                  children: [
                    CircleAvatar(
                      radius: 32,
                      backgroundColor: Colors.white,
                      child: Text(
                        account.initials,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w900,
                          color: C.brandDark,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            account.name.isEmpty ? 'UMS Mart shopper' : account.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            account.mobile,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          if (account.email.isNotEmpty)
                            Text(
                              account.email,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12.5,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Edit profile',
                      onPressed: () => showEditProfile(context),
                      icon: const Icon(Icons.edit_rounded, color: Colors.white),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _SupportRow extends StatelessWidget {
  const _SupportRow(this.icon, this.title, this.value);

  final IconData icon;
  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: C.brandSoft,
            child: Icon(icon, color: C.brand, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: C.muted,
                  ),
                ),
                SelectableText(
                  value,
                  style: const TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w800,
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
}

class _Menu extends StatelessWidget {
  const _Menu({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: C.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) const Divider(indent: 64),
            children[i],
          ],
        ],
      ),
    );
  }
}

class _MenuRow extends StatelessWidget {
  const _MenuRow({
    required this.icon,
    required this.title,
    required this.text,
    required this.onTap,
    this.color = C.brand,
  });

  final IconData icon;
  final String title;
  final String text;
  final VoidCallback onTap;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        child: Row(
          children: [
            Container(
              height: 38,
              width: 38,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 14.5,
                      fontWeight: FontWeight.w800,
                      color: color == C.rose ? C.rose : C.ink,
                    ),
                  ),
                  if (text.isNotEmpty)
                    Text(
                      text,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: C.muted,
                      ),
                    ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: C.muted),
          ],
        ),
      ),
    );
  }
}

// ------------------------------------------------------------ edit profile

Future<void> showEditProfile(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.white,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (_) => const _EditProfile(),
  );
}

class _EditProfile extends StatefulWidget {
  const _EditProfile();

  @override
  State<_EditProfile> createState() => _EditProfileState();
}

class _EditProfileState extends State<_EditProfile> {
  late final TextEditingController _name =
      TextEditingController(text: app.account?.name ?? '');
  late final TextEditingController _email =
      TextEditingController(text: app.account?.email ?? '');
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    if (name.length < 2) {
      setState(() => _error = 'Please enter your name.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await Api.updateProfile(name: name, email: _email.text.trim());
      await app.reloadAccount();
      if (!mounted) return;
      Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = errorText(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 22, 22, 22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Edit profile',
                style: TextStyle(
                    fontSize: 19, fontWeight: FontWeight.w900, color: C.ink),
              ),
              const SizedBox(height: 4),
              Text(
                'Mobile number ${app.account?.mobile ?? ''} cannot be changed.',
                style: const TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  color: C.muted,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(labelText: 'Full name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration:
                    const InputDecoration(labelText: 'Email (optional)'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
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
              BusyButton(label: 'Save', busy: _saving, onPressed: _save),
            ],
          ),
        ),
      ),
    );
  }
}

// --------------------------------------------------------------- addresses

class AddressesScreen extends StatefulWidget {
  const AddressesScreen({super.key});

  @override
  State<AddressesScreen> createState() => _AddressesScreenState();
}

class _AddressesScreenState extends State<AddressesScreen> {
  List<Address> _items = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await Api.addresses();
      if (!mounted) return;
      setState(() {
        _items = list;
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = errorText(e);
      });
    }
  }

  Future<void> _run(Future<void> Function() action, String done) async {
    try {
      await action();
      await _load();
      if (mounted) toast(context, done);
    } catch (e) {
      if (mounted) toast(context, errorText(e));
    }
  }

  Future<void> _add() async {
    final added = await showAddressForm(context);
    if (added == null) return;
    await _load();
    if (mounted) toast(context, 'Address saved');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Saved addresses')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _add,
        backgroundColor: C.brand,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add_rounded),
        label: const Text(
          'Add address',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: _loading
          ? const Loading()
          : _error != null && _items.isEmpty
              ? Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not load addresses',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                )
              : _items.isEmpty
                  ? const Notice(
                      icon: Icons.location_off_outlined,
                      title: 'No address saved',
                      text: 'Add one so we know where to deliver.',
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 96),
                      itemCount: _items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, i) {
                        final a = _items[i];
                        return Container(
                          padding: const EdgeInsets.fromLTRB(14, 14, 6, 6),
                          decoration: cardBox(),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: AddressText(address: a),
                              ),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.end,
                                children: [
                                  if (!a.isDefault)
                                    TextButton(
                                      onPressed: () => _run(
                                        () => Api.setDefaultAddress(a.id),
                                        'Default address changed',
                                      ),
                                      child: const Text('Make default'),
                                    ),
                                  TextButton(
                                    onPressed: () => _run(
                                      () => Api.removeAddress(a.id),
                                      'Address deleted',
                                    ),
                                    style: TextButton.styleFrom(
                                        foregroundColor: C.rose),
                                    child: const Text('Delete'),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        );
                      },
                    ),
    );
  }
}

// ---------------------------------------------------------------- wishlist

class WishlistScreen extends StatefulWidget {
  const WishlistScreen({super.key});

  @override
  State<WishlistScreen> createState() => _WishlistScreenState();
}

class _WishlistScreenState extends State<WishlistScreen> {
  List<Product> _items = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await Api.wishlist();
      await app.refreshWishlist();
      if (!mounted) return;
      setState(() {
        _items = list;
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = errorText(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Wishlist'),
        actions: const [CartAction(), SizedBox(width: 4)],
      ),
      body: _loading
          ? const Loading()
          : _error != null
              ? Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not load your wishlist',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                )
              : ListenableBuilder(
                  listenable: app,
                  builder: (context, _) {
                    // An item un-saved on this page leaves the list at once.
                    final shown = _items
                        .where((p) => app.wished.contains(p.id))
                        .toList();
                    if (shown.isEmpty) {
                      return Notice(
                        icon: Icons.favorite_border_rounded,
                        title: 'Nothing saved yet',
                        text: 'Tap the heart on any item to save it here.',
                        button: 'Browse products',
                        onButton: () => openHome(context),
                      );
                    }
                    return GridView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                      gridDelegate: productGrid,
                      itemCount: shown.length,
                      itemBuilder: (context, i) =>
                          ProductCard(product: shown[i]),
                    );
                  },
                ),
    );
  }
}
