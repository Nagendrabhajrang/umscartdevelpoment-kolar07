// Colours, the theme and the small building blocks every screen shares.

import 'package:flutter/material.dart';

import 'api.dart';
import 'models.dart';
import 'pics.dart';
import 'screens/login.dart';
import 'screens/product.dart';
import 'store.dart';

class C {
  static const Color brand = Color(0xFF0E9F4F);
  static const Color brandDark = Color(0xFF087A3B);
  static const Color brandSoft = Color(0xFFE8F7EE);
  static const Color ink = Color(0xFF101828);
  static const Color body = Color(0xFF344054);
  static const Color muted = Color(0xFF667085);
  static const Color line = Color(0xFFE7EAEE);
  static const Color bg = Color(0xFFF5F7F6);
  static const Color amber = Color(0xFFF59E0B);
  static const Color amberSoft = Color(0xFFFFF6E0);
  static const Color rose = Color(0xFFE11D48);
  static const Color roseSoft = Color(0xFFFFEEF1);
  static const Color blue = Color(0xFF2563EB);

  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF12B45A), Color(0xFF067A3A)],
  );
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: C.brand,
    primary: C.brand,
    surface: Colors.white,
  );
  final border = OutlineInputBorder(
    borderRadius: BorderRadius.circular(14),
    borderSide: const BorderSide(color: C.line),
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: C.bg,
    splashFactory: InkRipple.splashFactory,
    appBarTheme: const AppBarTheme(
      backgroundColor: C.bg,
      foregroundColor: C.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: C.ink,
        fontSize: 19,
        fontWeight: FontWeight.w800,
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: C.ink,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      contentTextStyle: const TextStyle(
        color: Colors.white,
        fontSize: 14,
        fontWeight: FontWeight.w600,
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
      hintStyle: const TextStyle(color: C.muted, fontWeight: FontWeight.w500),
      labelStyle: const TextStyle(color: C.muted, fontWeight: FontWeight.w600),
      border: border,
      enabledBorder: border,
      focusedBorder: border.copyWith(
        borderSide: const BorderSide(color: C.brand, width: 1.6),
      ),
      errorBorder: border.copyWith(
        borderSide: const BorderSide(color: C.rose),
      ),
      focusedErrorBorder: border.copyWith(
        borderSide: const BorderSide(color: C.rose, width: 1.6),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: C.brand,
        foregroundColor: Colors.white,
        disabledBackgroundColor: const Color(0xFFCBD5D1),
        disabledForegroundColor: Colors.white,
        minimumSize: const Size(0, 52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: C.brand,
        minimumSize: const Size(0, 48),
        side: const BorderSide(color: C.brand, width: 1.3),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: C.brand,
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800),
      ),
    ),
    dividerTheme: const DividerThemeData(color: C.line, thickness: 1, space: 1),
  );
}

// ------------------------------------------------------------------ helpers

String money(double value) {
  final whole = value == value.roundToDouble();
  return '₹${whole ? value.toStringAsFixed(0) : value.toStringAsFixed(2)}';
}

String dateText(DateTime? date) {
  if (date == null) return '';
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  final hour = date.hour % 12 == 0 ? 12 : date.hour % 12;
  final minute = date.minute.toString().padLeft(2, '0');
  final half = date.hour < 12 ? 'AM' : 'PM';
  return '${date.day} ${months[date.month - 1]} ${date.year}, $hour:$minute $half';
}

void toast(BuildContext context, String message) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(message),
      duration: const Duration(milliseconds: 1600),
    ));
}

/// Opens the cart tab from anywhere.
void openCart(BuildContext context) {
  Navigator.of(context).popUntil((route) => route.isFirst);
  app.tab.value = 2;
}

void openHome(BuildContext context) {
  Navigator.of(context).popUntil((route) => route.isFirst);
  app.tab.value = 0;
}

void openProduct(BuildContext context, Product product) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(builder: (_) => ProductScreen(product: product)),
  );
}

/// Makes sure the shopper is signed in. Returns true when they are.
Future<bool> requireLogin(BuildContext context) async {
  if (app.signedIn) return true;
  final ok = await Navigator.of(context).push<bool>(
    MaterialPageRoute<bool>(builder: (_) => const LoginScreen()),
  );
  return ok == true && app.signedIn;
}

BoxDecoration cardBox({double radius = 18, Color color = Colors.white}) {
  return BoxDecoration(
    color: color,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: C.line),
  );
}

// ------------------------------------------------------------------ picture

/// A picture from the server or from inside the app.
///
/// The whole picture is always shown (BoxFit.contain) on a white ground, so a
/// tall bottle or a wide pack is never cut at the edges.
class NetImage extends StatelessWidget {
  const NetImage(
    this.url, {
    super.key,
    this.label = '',
    this.radius = 14,
    this.fit = BoxFit.contain,
  });

  final String url;
  final String label;
  final double radius;
  final BoxFit fit;

  static const List<List<Color>> _tints = [
    [Color(0xFFDFF5E7), Color(0xFFBCE9CD)],
    [Color(0xFFFFF1D6), Color(0xFFFFE0A6)],
    [Color(0xFFE3EEFF), Color(0xFFC4DAFF)],
    [Color(0xFFFFE6EA), Color(0xFFFFC9D2)],
    [Color(0xFFEDE7FF), Color(0xFFD7CBFF)],
  ];

  Widget _fallback() {
    final clean = label.trim();
    final tint = _tints[clean.isEmpty ? 0 : clean.codeUnitAt(0) % _tints.length];
    final words =
        clean.split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    final letters = words.isEmpty
        ? ''
        : words.length == 1
            ? words.first[0]
            : words[0][0] + words[1][0];
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: tint,
        ),
      ),
      alignment: Alignment.center,
      child: letters.isEmpty
          ? const Icon(Icons.shopping_basket_outlined, color: Colors.white)
          : FittedBox(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Text(
                  letters.toUpperCase(),
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: C.ink.withValues(alpha: 0.35),
                  ),
                ),
              ),
            ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // A real photo from inside the app replaces the server's sample tile.
    final local = bundledPic(label, url);
    if (local != null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: ColoredBox(
          color: Colors.white,
          child: Image.asset(
            local,
            fit: fit,
            width: double.infinity,
            height: double.infinity,
            gaplessPlayback: true,
            errorBuilder: (_, __, ___) => _fallback(),
          ),
        ),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: url.isEmpty
          ? _fallback()
          : ColoredBox(
              color: Colors.white,
              child: Image.network(
                url,
                fit: fit,
                width: double.infinity,
                height: double.infinity,
                gaplessPlayback: true,
                errorBuilder: (_, __, ___) => _fallback(),
                loadingBuilder: (_, child, progress) =>
                    progress == null ? child : _fallback(),
              ),
            ),
    );
  }
}

// ------------------------------------------------------------- ADD button

/// The ADD button. It always says ADD: it never turns into a "- 1 +" control.
/// A tap puts one more of the item in the cart and shows "Item added to cart".
class AddButton extends StatefulWidget {
  const AddButton({super.key, required this.product, this.large = false});

  final Product product;
  final bool large;

  @override
  State<AddButton> createState() => _AddButtonState();
}

class _AddButtonState extends State<AddButton> {
  bool _busy = false;

  Future<void> _add() async {
    if (_busy) return;
    _busy = true;
    try {
      await app.addToCart(widget.product);
      if (mounted) toast(context, 'Item added to cart');
    } catch (e) {
      if (mounted) toast(context, errorText(e));
    } finally {
      _busy = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final soldOut = !widget.product.inStock;
    if (widget.large) {
      return FilledButton.icon(
        onPressed: soldOut ? null : _add,
        icon: const Icon(Icons.add_shopping_cart_rounded, size: 20),
        label: Text(soldOut ? 'Sold out' : 'Add to cart'),
      );
    }
    return Material(
      color: soldOut ? const Color(0xFFF1F3F5) : C.brandSoft,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: soldOut ? C.line : C.brand, width: 1.2),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: soldOut ? null : _add,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Text(
            soldOut ? 'SOLD OUT' : 'ADD',
            style: TextStyle(
              fontSize: soldOut ? 10.5 : 13,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.4,
              color: soldOut ? C.muted : C.brandDark,
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------- wishlist heart

class WishButton extends StatelessWidget {
  const WishButton({super.key, required this.productId, this.size = 34});

  final int productId;
  final double size;

  Future<void> _toggle(BuildContext context) async {
    if (!app.signedIn) {
      final ok = await requireLogin(context);
      if (!ok) return;
    }
    try {
      final saved = await app.toggleWish(productId);
      if (context.mounted) {
        toast(context, saved ? 'Saved to wishlist' : 'Removed from wishlist');
      }
    } catch (e) {
      if (context.mounted) toast(context, errorText(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final saved = app.wished.contains(productId);
        return Material(
          color: Colors.white.withValues(alpha: 0.92),
          shape: const CircleBorder(side: BorderSide(color: C.line)),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => _toggle(context),
            child: SizedBox(
              height: size,
              width: size,
              child: Icon(
                saved ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                size: size * 0.53,
                color: saved ? C.rose : C.muted,
              ),
            ),
          ),
        );
      },
    );
  }
}

// ----------------------------------------------------------- product card

class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    final p = product;
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: C.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => openProduct(context, p),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Stack(
                  children: [
                    Positioned.fill(
                      child: NetImage(p.image, label: p.name, radius: 12),
                    ),
                    if (p.discount > 0)
                      Positioned(
                        left: 6,
                        top: 6,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 7, vertical: 3),
                          decoration: BoxDecoration(
                            color: C.amber,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '${p.discount}% OFF',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                      ),
                    Positioned(
                      right: 6,
                      top: 6,
                      child: WishButton(productId: p.id, size: 30),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                height: 34,
                child: Text(
                  p.name,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    height: 1.25,
                    fontWeight: FontWeight.w700,
                    color: C.ink,
                  ),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                p.unit,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  color: C.muted,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          money(p.price),
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w900,
                            color: C.ink,
                          ),
                        ),
                        if (p.mrp > p.price)
                          Text(
                            money(p.mrp),
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: C.muted,
                              decoration: TextDecoration.lineThrough,
                            ),
                          ),
                      ],
                    ),
                  ),
                  AddButton(product: p),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

const SliverGridDelegate productGrid =
    SliverGridDelegateWithFixedCrossAxisCount(
  crossAxisCount: 2,
  mainAxisExtent: 258,
  crossAxisSpacing: 12,
  mainAxisSpacing: 12,
);

// ------------------------------------------------------------ small pieces

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.title, {super.key, this.action, this.onAction});

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 22, 8, 10),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w900,
                color: C.ink,
              ),
            ),
          ),
          if (action != null)
            TextButton(onPressed: onAction, child: Text(action!))
          else
            const SizedBox(height: 40),
        ],
      ),
    );
  }
}

class Loading extends StatelessWidget {
  const Loading({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: SizedBox(
        height: 30,
        width: 30,
        child: CircularProgressIndicator(strokeWidth: 3, color: C.brand),
      ),
    );
  }
}

/// A friendly full-screen message: empty states, errors, sign-in prompts.
class Notice extends StatelessWidget {
  const Notice({
    super.key,
    required this.icon,
    required this.title,
    this.text = '',
    this.button,
    this.onButton,
  });

  final IconData icon;
  final String title;
  final String text;
  final String? button;
  final VoidCallback? onButton;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              height: 92,
              width: 92,
              decoration: const BoxDecoration(
                color: C.brandSoft,
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 42, color: C.brand),
            ),
            const SizedBox(height: 18),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w900,
                color: C.ink,
              ),
            ),
            if (text.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                text,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 13.5,
                  height: 1.4,
                  fontWeight: FontWeight.w500,
                  color: C.muted,
                ),
              ),
            ],
            if (button != null) ...[
              const SizedBox(height: 20),
              FilledButton(
                onPressed: onButton,
                style: FilledButton.styleFrom(
                  minimumSize: const Size(180, 48),
                ),
                child: Text(button!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// A button that shows a spinner while its work is running.
class BusyButton extends StatelessWidget {
  const BusyButton({
    super.key,
    required this.label,
    required this.busy,
    required this.onPressed,
  });

  final String label;
  final bool busy;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        onPressed: busy ? null : onPressed,
        child: busy
            ? const SizedBox(
                height: 22,
                width: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.6,
                  color: Colors.white,
                ),
              )
            : Text(label),
      ),
    );
  }
}

/// Cart icon with the number of items on it. Opens the cart.
class CartAction extends StatelessWidget {
  const CartAction({super.key});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final count = app.cart.count;
        return IconButton(
          tooltip: 'Cart',
          onPressed: () => openCart(context),
          icon: Badge(
            isLabelVisible: count > 0,
            backgroundColor: C.rose,
            label: Text('$count'),
            child: const Icon(Icons.shopping_cart_outlined),
          ),
        );
      },
    );
  }
}

/// One line of the bill.
class BillRow extends StatelessWidget {
  const BillRow(this.label, this.value,
      {super.key, this.bold = false, this.color});

  final String label;
  final String value;
  final bool bold;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final style = TextStyle(
      fontSize: bold ? 16 : 13.5,
      fontWeight: bold ? FontWeight.w900 : FontWeight.w600,
      color: bold ? C.ink : C.body,
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(value, style: style.copyWith(color: color ?? style.color)),
        ],
      ),
    );
  }
}

/// The bill card used by the cart and the checkout.
class BillCard extends StatelessWidget {
  const BillCard({super.key, required this.bill});

  final Bill bill;

  @override
  Widget build(BuildContext context) {
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
          BillRow('Item total', money(bill.subtotal)),
          if (bill.discount > 0)
            BillRow(
              bill.coupon.isEmpty ? 'Offer discount' : 'Coupon ${bill.coupon}',
              '- ${money(bill.discount)}',
              color: C.brand,
            ),
          BillRow(
            'Delivery',
            bill.delivery == 0 ? 'FREE' : money(bill.delivery),
            color: bill.delivery == 0 ? C.brand : null,
          ),
          if (bill.packaging > 0) BillRow('Packaging', money(bill.packaging)),
          if (bill.tax > 0) BillRow('Taxes', money(bill.tax)),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Divider(),
          ),
          BillRow('To pay', money(bill.total), bold: true),
          if (bill.totalSavings > 0) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
              decoration: BoxDecoration(
                color: C.brandSoft,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                'You save ${money(bill.totalSavings)} on this order',
                style: const TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w800,
                  color: C.brandDark,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
