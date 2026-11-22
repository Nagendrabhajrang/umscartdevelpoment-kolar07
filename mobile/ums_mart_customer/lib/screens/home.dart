// Home tab: delivery header, search, offers, categories and product rows.

import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../pics.dart';
import '../store.dart';
import '../ui.dart';
import 'products.dart';
import 'profile.dart';

class HomeTab extends StatefulWidget {
  const HomeTab({super.key});

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  bool _loading = true;
  String? _error;
  List<BannerItem> _banners = const [];
  List<Category> _categories = const [];
  List<Product> _trending = const [];
  List<Product> _fresh = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<T> _safe<T>(Future<T> future, T fallback, List<Object> errors) async {
    try {
      return await future;
    } catch (e) {
      errors.add(e);
      return fallback;
    }
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = _trending.isEmpty && _fresh.isEmpty;
        _error = null;
      });
    }
    final errors = <Object>[];
    final results = await Future.wait<dynamic>([
      _safe<List<BannerItem>>(Api.banners(), const [], errors),
      _safe<List<Category>>(Api.categories(), const [], errors),
      _safe<List<Product>>(Api.featured(limit: 10), const [], errors),
      _safe<ProductPage>(
        Api.products(pageSize: 12, ordering: '-created_at'),
        ProductPage(const [], false),
        errors,
      ),
    ]);
    if (!mounted) return;
    setState(() {
      _banners = results[0] as List<BannerItem>;
      _categories = (results[1] as List<Category>)
          .where((c) => c.productCount > 0)
          .toList();
      _trending = results[2] as List<Product>;
      _fresh = (results[3] as ProductPage).items;
      _loading = false;
      _error = (_trending.isEmpty && _fresh.isEmpty && errors.isNotEmpty)
          ? errorText(errors.first)
          : null;
    });
    app.refreshCart();
  }

  void _openCategory(Category c) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => ProductsScreen(title: c.name, categoryId: c.id),
    ));
  }

  Future<void> _openBanner(BannerItem b) async {
    if (b.productId > 0) {
      try {
        final product = await Api.product(b.productId);
        if (mounted) openProduct(context, product);
      } catch (e) {
        if (mounted) toast(context, errorText(e));
      }
    } else if (b.categoryId > 0) {
      Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => ProductsScreen(
          title: b.title.isEmpty ? 'Offers' : b.title,
          categoryId: b.categoryId,
        ),
      ));
    } else if (b.coupon.isNotEmpty) {
      toast(context, 'Use code ${b.coupon} in your cart');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: RefreshIndicator(
        color: C.brand,
        onRefresh: _load,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            const SliverToBoxAdapter(child: _Header()),
            if (_loading)
              const SliverFillRemaining(hasScrollBody: false, child: Loading())
            else if (_error != null)
              SliverFillRemaining(
                hasScrollBody: false,
                child: Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not load the shop',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                ),
              )
            else ...[
              if (_banners.isNotEmpty)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: _Banners(items: _banners, onTap: _openBanner),
                  ),
                ),
              const SliverToBoxAdapter(child: _Perks()),
              if (_categories.isNotEmpty) ...[
                SliverToBoxAdapter(
                  child: SectionTitle(
                    'Shop by category',
                    action: 'See all',
                    onAction: () => app.tab.value = 1,
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  sliver: SliverGrid(
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 4,
                      mainAxisExtent: 104,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 10,
                    ),
                    delegate: SliverChildBuilderDelegate(
                      (context, i) => _CategoryTile(
                        category: _categories[i],
                        onTap: () => _openCategory(_categories[i]),
                      ),
                      childCount:
                          _categories.length > 8 ? 8 : _categories.length,
                    ),
                  ),
                ),
              ],
              if (_trending.isNotEmpty) ...[
                SliverToBoxAdapter(
                  child: SectionTitle(
                    'Trending now',
                    action: 'See all',
                    onAction: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const ProductsScreen(
                            title: 'Trending now', featured: true),
                      ),
                    ),
                  ),
                ),
                SliverToBoxAdapter(
                  child: SizedBox(
                    height: 258,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      itemCount: _trending.length,
                      separatorBuilder: (_, __) => const SizedBox(width: 12),
                      itemBuilder: (context, i) => SizedBox(
                        width: 164,
                        child: ProductCard(product: _trending[i]),
                      ),
                    ),
                  ),
                ),
              ],
              if (_fresh.isNotEmpty) ...[
                SliverToBoxAdapter(
                  child: SectionTitle(
                    'Fresh arrivals',
                    action: 'See all',
                    onAction: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) =>
                            const ProductsScreen(title: 'All products'),
                      ),
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  sliver: SliverGrid(
                    gridDelegate: productGrid,
                    delegate: SliverChildBuilderDelegate(
                      (context, i) => ProductCard(product: _fresh[i]),
                      childCount: _fresh.length,
                    ),
                  ),
                ),
              ],
              const SliverToBoxAdapter(child: SizedBox(height: 28)),
            ],
          ],
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ header

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: C.brandGradient,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(26)),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: ListenableBuilder(
                      listenable: app,
                      builder: (context, _) {
                        final name = app.account?.name ?? '';
                        final first = name.trim().split(' ').first;
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              first.isEmpty ? 'Welcome to' : 'Hello, $first',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              app.settings.name,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 24,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ],
                        );
                      },
                    ),
                  ),
                  _RoundIcon(
                    icon: Icons.favorite_border_rounded,
                    onTap: () async {
                      final ok = await requireLogin(context);
                      if (!ok || !context.mounted) return;
                      Navigator.of(context).push(MaterialPageRoute<void>(
                        builder: (_) => const WishlistScreen(),
                      ));
                    },
                  ),
                ],
              ),
              const SizedBox(height: 10),
              ListenableBuilder(
                listenable: app,
                builder: (context, _) => Row(
                  children: [
                    const Icon(Icons.bolt_rounded,
                        color: Color(0xFFFFE08A), size: 18),
                    const SizedBox(width: 4),
                    Text(
                      'Delivery in ${app.settings.etaMinutes} minutes',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                        builder: (_) => const SearchScreen()),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                    child: Row(
                      children: [
                        Icon(Icons.search_rounded, color: C.brand),
                        SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Search milk, atta, fruits...',
                            style: TextStyle(
                              color: C.muted,
                              fontSize: 14.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoundIcon extends StatelessWidget {
  const _RoundIcon({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.18),
      shape: const CircleBorder(),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: SizedBox(
          height: 44,
          width: 44,
          child: Icon(icon, color: Colors.white, size: 22),
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ offers

class _Banners extends StatefulWidget {
  const _Banners({required this.items, required this.onTap});

  final List<BannerItem> items;
  final void Function(BannerItem) onTap;

  @override
  State<_Banners> createState() => _BannersState();
}

class _BannersState extends State<_Banners> {
  final PageController _pages = PageController(viewportFraction: 0.9);
  Timer? _timer;
  int _index = 0;

  static const List<List<Color>> _looks = [
    [Color(0xFF0F766E), Color(0xFF14B8A6)],
    [Color(0xFFEA580C), Color(0xFFF59E0B)],
    [Color(0xFF4338CA), Color(0xFF7C3AED)],
    [Color(0xFFBE123C), Color(0xFFF43F5E)],
  ];

  @override
  void initState() {
    super.initState();
    if (widget.items.length > 1) {
      _timer = Timer.periodic(const Duration(seconds: 4), (_) {
        if (!mounted || !_pages.hasClients) return;
        final next = (_index + 1) % widget.items.length;
        _pages.animateToPage(
          next,
          duration: const Duration(milliseconds: 450),
          curve: Curves.easeOut,
        );
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pages.dispose();
    super.dispose();
  }

  /// The banner photo with a colour fade over it, so the words stay readable.
  List<Widget> _photo(BannerItem b, List<Color> look) {
    final local = bundledBanner(b);
    if (local == null && b.image.isEmpty) return const <Widget>[];
    Widget gone(BuildContext _, Object __, StackTrace? ___) =>
        const SizedBox.shrink();
    final Widget picture = local != null
        ? Image.asset(local,
            fit: BoxFit.cover,
            alignment: Alignment.centerRight,
            errorBuilder: gone)
        : Image.network(b.image,
            fit: BoxFit.cover,
            alignment: Alignment.centerRight,
            errorBuilder: gone);
    return <Widget>[
      Positioned.fill(child: picture),
      Positioned.fill(
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                look[0].withValues(alpha: 0.97),
                look[0].withValues(alpha: 0.80),
                look[0].withValues(alpha: 0.10),
              ],
              stops: const [0, 0.52, 1],
            ),
          ),
        ),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          height: 156,
          child: PageView.builder(
            controller: _pages,
            itemCount: widget.items.length,
            onPageChanged: (i) => setState(() => _index = i),
            itemBuilder: (context, i) {
              final b = widget.items[i];
              final look = _looks[i % _looks.length];
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 5),
                child: GestureDetector(
                  onTap: () => widget.onTap(b),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(22),
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        DecoratedBox(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: look,
                            ),
                          ),
                        ),
                        Positioned(
                          right: -30,
                          top: -30,
                          child: Container(
                            height: 150,
                            width: 150,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: Colors.white.withValues(alpha: 0.12),
                            ),
                          ),
                        ),
                        Positioned(
                          right: 30,
                          bottom: -50,
                          child: Container(
                            height: 120,
                            width: 120,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: Colors.white.withValues(alpha: 0.10),
                            ),
                          ),
                        ),
                        ..._photo(b, look),
                        Padding(
                          padding: const EdgeInsets.fromLTRB(18, 16, 90, 16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 9, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.22),
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Text(
                                  b.coupon.isEmpty
                                      ? 'TODAY\'S OFFER'
                                      : 'CODE ${b.coupon}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 10.5,
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: 0.6,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 10),
                              Text(
                                b.title.isEmpty ? 'Fresh deals' : b.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 22,
                                  fontWeight: FontWeight.w900,
                                ),
                              ),
                              if (b.subtitle.isNotEmpty) ...[
                                const SizedBox(height: 4),
                                Text(
                                  b.subtitle,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 13,
                                    height: 1.3,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                        const Positioned(
                          right: 18,
                          bottom: 16,
                          child: CircleAvatar(
                            radius: 18,
                            backgroundColor: Colors.white,
                            child: Icon(Icons.arrow_forward_rounded,
                                color: C.ink, size: 20),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        if (widget.items.length > 1) ...[
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (var i = 0; i < widget.items.length; i++)
                AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  height: 6,
                  width: i == _index ? 20 : 6,
                  decoration: BoxDecoration(
                    color: i == _index ? C.brand : const Color(0xFFD0D5DD),
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _Perks extends StatelessWidget {
  const _Perks();

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final free = app.settings.freeDeliveryAbove;
        final items = <(IconData, Color, String, String)>[
          (
            Icons.bolt_rounded,
            C.amber,
            '${app.settings.etaMinutes} min',
            'Fast delivery'
          ),
          (
            Icons.payments_rounded,
            C.brand,
            'Cash',
            'Pay on delivery'
          ),
          (
            Icons.local_shipping_rounded,
            C.blue,
            free > 0 ? 'Free' : 'Fresh',
            free > 0 ? 'Above ${money(free)}' : 'Every day'
          ),
        ];
        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
          child: Row(
            children: [
              for (var i = 0; i < items.length; i++) ...[
                if (i > 0) const SizedBox(width: 10),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: cardBox(radius: 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(items[i].$1, color: items[i].$2, size: 22),
                        const SizedBox(height: 8),
                        Text(
                          items[i].$3,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w900,
                            color: C.ink,
                          ),
                        ),
                        Text(
                          items[i].$4,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: C.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile({required this.category, required this.onTap});

  final Category category;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Column(
        children: [
          Expanded(
            child: AspectRatio(
              aspectRatio: 1,
              child:
                  NetImage(category.image, label: category.name, radius: 18),
            ),
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 30,
            child: Text(
              category.name,
              maxLines: 2,
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 11,
                height: 1.25,
                fontWeight: FontWeight.w700,
                color: C.ink,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
