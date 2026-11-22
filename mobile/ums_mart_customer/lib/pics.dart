// Real pictures that ship inside the app.
//
// The sample data on the server only has plain colour tiles with two letters
// as pictures. For those the app shows a real photo from assets/pics instead.
// As soon as a real picture is uploaded in the admin panel, the app shows the
// uploaded picture, not the one from here.
//
// A photo is found by the name of the product or category:
//   "Amul Butter"        -> assets/pics/p/amul-butter.jpg
//   "Biscuits & Cookies" -> assets/pics/c/biscuits-cookies.jpg
// To add one, put the file in the folder and add its name to the list below.

import 'models.dart' show BannerItem;

const Set<String> _productPics = <String>{
  'aashirvaad-shudh-chakki-atta',
  'amul-butter',
  'amul-cheese-slices',
  'amul-fresh-paneer',
  'amul-masti-dahi',
  'amul-pure-ghee',
  'amul-taaza-toned-milk',
  'ariel-matic-liquid',
  'baby-spinach',
  'banana-robusta',
  'bansi-rava',
  'bisleri-mineral-water',
  'britannia-brown-bread',
  'bru-instant-coffee',
  'cadbury-dairy-milk-silk',
  'carrot',
  'coca-cola',
  'colgate-strong-teeth',
  'colin-glass-cleaner',
  'coriander-leaves',
  'dettol-liquid-handwash',
  'dove-cream-beauty-bar',
  'everest-garam-masala',
  'everest-turmeric-powder',
  'farm-eggs-6-pcs',
  'fortune-sunlite-sunflower-oil',
  'ginger',
  'good-day-cashew-cookies',
  'green-capsicum',
  'green-chilli',
  'green-grapes',
  'haldirams-aloo-bhujia',
  'harpic-toilet-cleaner',
  'head-shoulders-shampoo',
  'india-gate-basmati-rice',
  'kabuli-chana',
  'kelloggs-corn-flakes',
  'kissan-fresh-tomato-ketchup',
  'kurkure-masala-munch',
  'lays-classic-salted',
  'lemon',
  'lizol-floor-cleaner',
  'maggi-2-minute-noodles',
  'mango-frooti',
  'mint-leaves',
  'moong-dal-yellow',
  'nagpur-orange',
  'nescafe-classic',
  'nestle-kitkat',
  'onion',
  'oreo-vanilla-creme-biscuits',
  'parle-g-biscuits',
  'pomegranate',
  'potato',
  'quaker-oats',
  'real-mixed-fruit-juice',
  'saffola-gold-oil',
  'shimla-apple',
  'sona-masoori-rice',
  'surf-excel-easy-wash',
  'tata-salt',
  'tata-tea-premium',
  'tide-plus-detergent-powder',
  'tomato-local',
  'toor-dal',
  'vim-dishwash-gel',
};

const Set<String> _categoryPics = <String>{
  'atta-flours',
  'biscuits-cookies',
  'bread-eggs',
  'breakfast-cereals',
  'butter-cheese',
  'chips-namkeen',
  'chocolates-sweets',
  'cleaning-supplies',
  'cold-drinks-juices',
  'dairy-breakfast',
  'dal-pulses',
  'detergents',
  'fresh-fruits',
  'fresh-vegetables',
  'fruits-vegetables',
  'herbs-seasonings',
  'home-personal-care',
  'masalas-spices',
  'milk-curd',
  'noodles-sauces',
  'oils-ghee',
  'rice-rice-products',
  'snacks-beverages',
  'soaps-shampoos',
  'staples-grains',
  'tea-coffee',
};

/// "Haldiram's Aloo Bhujia" -> "haldirams-aloo-bhujia".
String slugOf(String name) => name
    .toLowerCase()
    .replaceAll(RegExp(r'[^a-z0-9\s-]'), '')
    .trim()
    .replaceAll(RegExp(r'[\s-]+'), '-');

final RegExp _sampleFile = RegExp(r'^((p|g|c|b)_[^/]*\.png|banner_[^/]*)$');

/// True when the server has no picture, or only the sample colour tile.
bool isSamplePicture(String url) {
  if (url.isEmpty) return true;
  final path = Uri.tryParse(url)?.path ?? url;
  final file = path.split('/').last;
  return _sampleFile.hasMatch(file);
}

/// The photo inside the app for this product or category, or null when the
/// server picture must be used.
String? bundledPic(String label, String url) {
  if (!isSamplePicture(url)) return null;
  final slug = slugOf(label);
  if (slug.isEmpty) return null;
  if (_productPics.contains(slug)) return 'assets/pics/p/$slug.jpg';
  if (_categoryPics.contains(slug)) return 'assets/pics/c/$slug.jpg';
  return null;
}

/// The photo inside the app for an offer banner, or null when the banner has
/// its own uploaded picture.
String? bundledBanner(BannerItem b) {
  if (!isSamplePicture(b.image)) return null;
  if (b.coupon.isNotEmpty) return 'assets/pics/b/offer.png';
  final text = '${b.title} ${b.subtitle}'.toLowerCase();
  if (RegExp(r'staple|rice|atta|dal|grain|flour').hasMatch(text)) {
    return 'assets/pics/b/staples.jpg';
  }
  return 'assets/pics/b/fresh.jpg';
}
