// Categories tab: main groups on the left, their sections on the right.

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../ui.dart';
import 'products.dart';

class CategoriesTab extends StatefulWidget {
  const CategoriesTab({super.key});

  @override
  State<CategoriesTab> createState() => _CategoriesTabState();
}

class _CategoriesTabState extends State<CategoriesTab> {
  bool _loading = true;
  String? _error;
  List<Category> _all = const [];
  int _selected = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final all = await Api.categories();
      if (!mounted) return;
      setState(() {
        _all = all;
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

  /// Main groups. If the shop has no groups, every category is a group.
  List<Category> get _parents {
    final top = _all.where((c) => c.parentId == 0).toList();
    return top.isEmpty ? _all : top;
  }

  List<Category> _children(Category parent) =>
      _all.where((c) => c.parentId == parent.id).toList();

  void _open(Category c) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => ProductsScreen(title: c.name, categoryId: c.id),
    ));
  }

  static IconData _iconFor(Category c) {
    final key = '${c.icon} ${c.name}'.toLowerCase();
    if (key.contains('carrot') || key.contains('fruit') || key.contains('veg')) {
      return Icons.eco_rounded;
    }
    if (key.contains('milk') || key.contains('dairy')) {
      return Icons.local_drink_rounded;
    }
    if (key.contains('rice') || key.contains('staple') || key.contains('grain')) {
      return Icons.rice_bowl_rounded;
    }
    if (key.contains('cookie') || key.contains('snack')) {
      return Icons.cookie_rounded;
    }
    if (key.contains('sparkle') || key.contains('care') || key.contains('home')) {
      return Icons.auto_awesome_rounded;
    }
    return Icons.category_rounded;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Categories'),
        actions: [
          IconButton(
            tooltip: 'Search',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SearchScreen()),
            ),
            icon: const Icon(Icons.search_rounded),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: _loading
          ? const Loading()
          : _error != null
              ? Notice(
                  icon: Icons.wifi_off_rounded,
                  title: 'Could not load categories',
                  text: _error!,
                  button: 'Try again',
                  onButton: _load,
                )
              : _all.isEmpty
                  ? const Notice(
                      icon: Icons.category_outlined,
                      title: 'No categories yet',
                      text: 'Categories added in the admin panel show up here.',
                    )
                  : _content(),
    );
  }

  Widget _content() {
    final parents = _parents;
    final index = _selected < parents.length ? _selected : 0;
    final parent = parents[index];
    final children = _children(parent);
    final tiles = children.isEmpty ? <Category>[parent] : children;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 92,
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(right: BorderSide(color: C.line)),
          ),
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: parents.length,
            itemBuilder: (context, i) {
              final active = i == index;
              return InkWell(
                onTap: () => setState(() => _selected = i),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
                  decoration: BoxDecoration(
                    color: active ? C.brandSoft : Colors.transparent,
                    border: Border(
                      left: BorderSide(
                        color: active ? C.brand : Colors.transparent,
                        width: 4,
                      ),
                    ),
                  ),
                  child: Column(
                    children: [
                      Container(
                        height: 46,
                        width: 46,
                        decoration: BoxDecoration(
                          color: active ? C.brand : C.bg,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          _iconFor(parents[i]),
                          color: active ? Colors.white : C.muted,
                          size: 24,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        parents[i].name,
                        maxLines: 2,
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 11,
                          height: 1.2,
                          fontWeight:
                              active ? FontWeight.w900 : FontWeight.w600,
                          color: active ? C.brandDark : C.body,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(14),
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      parent.name,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w900,
                        color: C.ink,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: () => _open(parent),
                    child: const Text('View all'),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisExtent: 168,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                ),
                itemCount: tiles.length,
                itemBuilder: (context, i) {
                  final c = tiles[i];
                  return Material(
                    color: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                      side: const BorderSide(color: C.line),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: () => _open(c),
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: NetImage(c.image,
                                  label: c.name, radius: 12),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              c.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w800,
                                color: C.ink,
                              ),
                            ),
                            Text(
                              c.productCount == 1
                                  ? '1 item'
                                  : '${c.productCount} items',
                              style: const TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w600,
                                color: C.muted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ],
    );
  }
}
