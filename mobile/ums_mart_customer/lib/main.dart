// UMS Mart customer app.
// Opens with a short loading screen, then the five tabs:
// Home, Categories, Cart, Orders, Profile.

import 'package:flutter/material.dart';

import 'screens/cart.dart';
import 'screens/categories.dart';
import 'screens/home.dart';
import 'screens/orders.dart';
import 'screens/profile.dart';
import 'store.dart';
import 'ui.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const UmsApp());
}

class UmsApp extends StatelessWidget {
  const UmsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'UMS Mart',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const BootScreen(),
    );
  }
}

class BootScreen extends StatefulWidget {
  const BootScreen({super.key});

  @override
  State<BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen> {
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    app.boot().whenComplete(() {
      if (mounted) setState(() => _ready = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_ready) return const Shell();
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: C.brandGradient),
        alignment: Alignment.center,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              height: 96,
              width: 96,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(28),
              ),
              child: const Icon(Icons.shopping_basket_rounded,
                  size: 52, color: C.brand),
            ),
            const SizedBox(height: 20),
            const Text(
              'UMS Mart',
              style: TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Fresh groceries to your door',
              style: TextStyle(
                color: Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 28),
            const SizedBox(
              height: 26,
              width: 26,
              child: CircularProgressIndicator(
                  strokeWidth: 2.8, color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}

class Shell extends StatelessWidget {
  const Shell({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int>(
      valueListenable: app.tab,
      builder: (context, index, _) {
        return PopScope(
          // The phone's back button returns to Home before closing the app.
          canPop: index == 0,
          onPopInvokedWithResult: (didPop, _) {
            if (!didPop) app.tab.value = 0;
          },
          child: Scaffold(
            body: IndexedStack(
              index: index,
              children: const [
                HomeTab(),
                CategoriesTab(),
                CartTab(),
                OrdersTab(),
                ProfileTab(),
              ],
            ),
            bottomNavigationBar: ListenableBuilder(
              listenable: app,
              builder: (context, _) {
                final count = app.cart.count;
                return DecoratedBox(
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    border: Border(top: BorderSide(color: C.line)),
                  ),
                  child: NavigationBar(
                    height: 66,
                    elevation: 0,
                    backgroundColor: Colors.white,
                    surfaceTintColor: Colors.transparent,
                    indicatorColor: C.brandSoft,
                    selectedIndex: index,
                    onDestinationSelected: (i) => app.tab.value = i,
                    destinations: [
                      const NavigationDestination(
                        icon: Icon(Icons.home_outlined),
                        selectedIcon: Icon(Icons.home_rounded, color: C.brand),
                        label: 'Home',
                      ),
                      const NavigationDestination(
                        icon: Icon(Icons.grid_view_outlined),
                        selectedIcon:
                            Icon(Icons.grid_view_rounded, color: C.brand),
                        label: 'Categories',
                      ),
                      NavigationDestination(
                        icon: Badge(
                          isLabelVisible: count > 0,
                          backgroundColor: C.rose,
                          label: Text('$count'),
                          child: const Icon(Icons.shopping_cart_outlined),
                        ),
                        selectedIcon: Badge(
                          isLabelVisible: count > 0,
                          backgroundColor: C.rose,
                          label: Text('$count'),
                          child: const Icon(Icons.shopping_cart_rounded,
                              color: C.brand),
                        ),
                        label: 'Cart',
                      ),
                      const NavigationDestination(
                        icon: Icon(Icons.receipt_long_outlined),
                        selectedIcon:
                            Icon(Icons.receipt_long_rounded, color: C.brand),
                        label: 'Orders',
                      ),
                      const NavigationDestination(
                        icon: Icon(Icons.person_outline_rounded),
                        selectedIcon:
                            Icon(Icons.person_rounded, color: C.brand),
                        label: 'Profile',
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        );
      },
    );
  }
}
