// One product: pictures, price, details and similar items.

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../pics.dart';
import '../store.dart';
import '../ui.dart';

class ProductScreen extends StatefulWidget {
  const ProductScreen({super.key, required this.product});

  final Product product;

  @override
  State<ProductScreen> createState() => _ProductScreenState();
}

class _ProductScreenState extends State<ProductScreen> {
  late Product _product = widget.product;
  List<Product> _related = const [];
  int _photo = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final full = await Api.product(widget.product.id);
      if (mounted) setState(() => _product = full);
    } catch (_) {
      // The card's own data is enough to show the page.
    }
    try {
      final related = await Api.related(widget.product.id);
      if (mounted) {
        setState(() => _related =
            related.where((e) => e.id != widget.product.id).toList());
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final p = _product;
    var photos = p.gallery.isEmpty ? <String>[''] : p.gallery;
    if (bundledPic(p.name, photos.first) != null) {
      // The app has a real photo for this product: show it once, followed by
      // any real pictures uploaded on the server (not the sample tiles).
      photos = <String>[
        photos.first,
        ...photos.skip(1).where((u) => !isSamplePicture(u)),
      ];
    }

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 4),
            child: Center(child: WishButton(productId: p.id, size: 38)),
          ),
          const CartAction(),
          const SizedBox(width: 4),
        ],
      ),
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          SizedBox(
            height: 300,
            child: Stack(
              children: [
                PageView.builder(
                  itemCount: photos.length,
                  onPageChanged: (i) => setState(() => _photo = i),
                  itemBuilder: (context, i) => Padding(
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                    child: NetImage(photos[i], label: p.name, radius: 24),
                  ),
                ),
                if (p.discount > 0)
                  Positioned(
                    left: 28,
                    top: 16,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: C.amber,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${p.discount}% OFF',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
                if (photos.length > 1)
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 18,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        for (var i = 0; i < photos.length; i++)
                          Container(
                            margin: const EdgeInsets.symmetric(horizontal: 3),
                            height: 7,
                            width: i == _photo ? 20 : 7,
                            decoration: BoxDecoration(
                              color: i == _photo
                                  ? C.brand
                                  : Colors.white.withValues(alpha: 0.9),
                              borderRadius: BorderRadius.circular(7),
                              border: Border.all(color: C.line),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (p.brand.isNotEmpty)
                  Text(
                    p.brand.toUpperCase(),
                    style: const TextStyle(
                      fontSize: 11.5,
                      letterSpacing: 0.8,
                      fontWeight: FontWeight.w900,
                      color: C.brand,
                    ),
                  ),
                const SizedBox(height: 4),
                Text(
                  p.name,
                  style: const TextStyle(
                    fontSize: 22,
                    height: 1.2,
                    fontWeight: FontWeight.w900,
                    color: C.ink,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (p.unit.isNotEmpty) _Tag(Icons.scale_outlined, p.unit),
                    _Tag(
                      Icons.circle,
                      p.isVeg ? 'Vegetarian' : 'Non-vegetarian',
                      color: p.isVeg ? C.brand : C.rose,
                    ),
                    _Tag(
                      p.inStock
                          ? Icons.check_circle_outline_rounded
                          : Icons.block_rounded,
                      p.inStock ? 'In stock' : 'Sold out',
                      color: p.inStock ? C.brand : C.rose,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      money(p.price),
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w900,
                        color: C.ink,
                      ),
                    ),
                    if (p.mrp > p.price) ...[
                      const SizedBox(width: 10),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 5),
                        child: Text(
                          money(p.mrp),
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: C.muted,
                            decoration: TextDecoration.lineThrough,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                if (p.saving > 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      'You save ${money(p.saving)}',
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: C.brand,
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                ListenableBuilder(
                  listenable: app,
                  builder: (context, _) => Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: C.brandSoft,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.bolt_rounded, color: C.brand),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Delivered in about ${app.settings.etaMinutes} minutes. Pay cash on delivery.',
                            style: const TextStyle(
                              fontSize: 13,
                              height: 1.35,
                              fontWeight: FontWeight.w700,
                              color: C.brandDark,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                if (p.description.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  const Text(
                    'About this item',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      color: C.ink,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    p.description,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.5,
                      fontWeight: FontWeight.w500,
                      color: C.body,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (_related.isNotEmpty) ...[
            const SectionTitle('You may also like'),
            SizedBox(
              height: 258,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _related.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (context, i) => SizedBox(
                  width: 164,
                  child: ProductCard(product: _related[i]),
                ),
              ),
            ),
          ],
          const SizedBox(height: 28),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: C.line)),
        ),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 10),
            child: Row(
              children: [
                Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      money(p.price),
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                        color: C.ink,
                      ),
                    ),
                    Text(
                      p.unit.isEmpty ? 'per pack' : p.unit,
                      style: const TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: C.muted,
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 18),
                Expanded(child: AddButton(product: p, large: true)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.icon, this.text, {this.color = C.body});

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: C.bg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: C.line),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 5),
          Text(
            text,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: C.body,
            ),
          ),
        ],
      ),
    );
  }
}
