// Product lists: a category's products, "see all" lists, and search.

import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../ui.dart';

class ProductsScreen extends StatefulWidget {
  const ProductsScreen({
    super.key,
    required this.title,
    this.categoryId,
    this.featured = false,
  });

  final String title;
  final int? categoryId;
  final bool featured;

  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  final ScrollController _scroll = ScrollController();
  final List<Product> _items = [];
  bool _loading = true;
  bool _more = false;
  bool _loadingMore = false;
  String? _error;
  int _page = 1;
  String? _ordering;

  static const Map<String, String?> _sorts = {
    'Popular': null,
    'Price: low to high': 'selling_price',
    'Price: high to low': '-selling_price',
    'Newest first': '-created_at',
  };

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 400) {
        _loadMore();
      }
    });
    _load();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<ProductPage> _fetch(int page) => Api.products(
        page: page,
        category: widget.categoryId,
        featured: widget.featured,
        ordering: _ordering,
      );

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _fetch(1);
      if (!mounted) return;
      setState(() {
        _items
          ..clear()
          ..addAll(result.items);
        _page = 1;
        _more = result.hasMore;
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

  Future<void> _loadMore() async {
    if (!_more || _loadingMore || _loading) return;
    _loadingMore = true;
    try {
      final result = await _fetch(_page + 1);
      if (!mounted) return;
      setState(() {
        _items.addAll(result.items);
        _page += 1;
        _more = result.hasMore;
      });
    } catch (_) {
      // The list simply stops growing; pulling down reloads it.
    } finally {
      _loadingMore = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Sort',
            icon: const Icon(Icons.sort_rounded),
            onSelected: (label) {
              _ordering = _sorts[label];
              _load();
            },
            itemBuilder: (_) => [
              for (final label in _sorts.keys)
                PopupMenuItem<String>(
                  value: label,
                  child: Text(
                    label,
                    style: TextStyle(
                      fontWeight: _sorts[label] == _ordering
                          ? FontWeight.w900
                          : FontWeight.w500,
                    ),
                  ),
                ),
            ],
          ),
          const CartAction(),
          const SizedBox(width: 4),
        ],
      ),
      body: _loading
          ? const Loading()
          : _error != null
              ? Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not load products',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                )
              : _items.isEmpty
                  ? const Notice(
                      icon: Icons.inventory_2_outlined,
                      title: 'Nothing here yet',
                      text: 'Products in this section will show up here.',
                    )
                  : RefreshIndicator(
                      color: C.brand,
                      onRefresh: _load,
                      child: GridView.builder(
                        controller: _scroll,
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                        gridDelegate: productGrid,
                        itemCount: _items.length,
                        itemBuilder: (context, i) =>
                            ProductCard(product: _items[i]),
                      ),
                    ),
    );
  }
}

// ------------------------------------------------------------------ search

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TextEditingController _text = TextEditingController();
  Timer? _wait;
  List<Product> _items = const [];
  bool _loading = false;
  String? _error;
  String _asked = '';

  static const List<String> _ideas = [
    'Milk', 'Rice', 'Atta', 'Bread', 'Butter', 'Tea', 'Banana', 'Soap',
  ];

  @override
  void dispose() {
    _wait?.cancel();
    _text.dispose();
    super.dispose();
  }

  void _changed(String value) {
    _wait?.cancel();
    _wait = Timer(const Duration(milliseconds: 350), () => _search(value));
    setState(() {});
  }

  Future<void> _search(String value) async {
    final query = value.trim();
    _asked = query;
    if (query.isEmpty) {
      setState(() {
        _items = const [];
        _loading = false;
        _error = null;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await Api.products(search: query, pageSize: 40);
      if (!mounted || _asked != query) return;
      setState(() {
        _items = result.items;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || _asked != query) return;
      setState(() {
        _error = errorText(e);
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final query = _text.text.trim();
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Padding(
          padding: const EdgeInsets.only(right: 8),
          child: TextField(
            controller: _text,
            autofocus: true,
            textInputAction: TextInputAction.search,
            onChanged: _changed,
            onSubmitted: _search,
            decoration: InputDecoration(
              hintText: 'Search for products',
              isDense: true,
              prefixIcon: const Icon(Icons.search_rounded, color: C.brand),
              suffixIcon: query.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.close_rounded),
                      onPressed: () {
                        _text.clear();
                        _changed('');
                      },
                    ),
            ),
          ),
        ),
        actions: const [CartAction(), SizedBox(width: 4)],
      ),
      body: query.isEmpty
          ? ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text(
                  'Popular searches',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: C.ink,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final idea in _ideas)
                      ActionChip(
                        label: Text(idea),
                        backgroundColor: Colors.white,
                        side: const BorderSide(color: C.line),
                        labelStyle: const TextStyle(
                          fontWeight: FontWeight.w700,
                          color: C.body,
                        ),
                        onPressed: () {
                          _text.text = idea;
                          _search(idea);
                        },
                      ),
                  ],
                ),
              ],
            )
          : _loading
              ? const Loading()
              : _error != null
                  ? Notice(
                      icon: Icons.wifi_off_rounded,
                      title: 'Search did not work',
                      text: _error!,
                      button: 'Try again',
                      onButton: () => _search(_text.text),
                    )
                  : _items.isEmpty
                      ? Notice(
                          icon: Icons.search_off_rounded,
                          title: 'No results for "$query"',
                          text: 'Try a shorter or different word.',
                        )
                      : GridView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                          gridDelegate: productGrid,
                          itemCount: _items.length,
                          itemBuilder: (context, i) =>
                              ProductCard(product: _items[i]),
                        ),
    );
  }
}
