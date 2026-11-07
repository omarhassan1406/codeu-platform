# Riverpod Mastery
## Asynchronous State with AsyncValue

# منصة CodeU التعليمية 🚀
## الكورس: Advanced Flutter State Management & Clean Architecture
### القسم: Riverpod Mastery | الدرس: [3.2] Asynchronous State with AsyncValue

---

## 1. المقدمة (Introduction)

أهلاً بك أيها المبرمج المبدع في درس جديد من مسحوق إدارة الحالة المتقدم في Flutter. في التطبيقات الحقيقية، بياناتنا لا تأتي من الذاكرة المحلية فوراً، بل تمر برحلة عبر الشبكة (Network) أو قواعد البيانات، وهذه الرحلة تحمل معها 3 حالات أساسية:
1. **جارِ التحميل (Loading)**
2. **حدث خطأ (Error)**
3. **تم جلب البيانات بنجاح (Data)**

في الماضي، كنا نكتب الكثير من متغيرات الـ `bool isLoading` و `String? error` و `T? data` وندخل في متاهات الـ `if-else`. 
لكن مع **Riverpod**، يأتي كائن السحر الحلال **`AsyncValue`** ليوفر علينا كل هذا العناء، ويجبرنا برمجياً على التعامل مع الحالات الثلاث بطريقة تصريحية (Declarative) ونظيفة جداً.

---

## 2. الشرح العميق لـ AsyncValue (Deep Dive)

ما هو `AsyncValue<T>` فعلياً؟ هو عبارة عن `Sealed Class` في Dart يمثل حالة عملية غير جynchronous (غير متزامنة). يحتوي على ثلاثة أنواع فرعية (Subclasses):

* `AsyncLoading<T>()`: تعني أن الطلب قيد التنفيذ الآن. (ملاحظة: قد تكون البيانات القديمة متوفرة في حالة الـ Refresh).
* `AsyncError<T>`: تحمل الخطأ `Object error` و `StackTrace stackTrace`.
* `AsyncData<T>`: تحمل القيمة المطلوبة من النوع `T`.

### الـ Methods السحرية في AsyncValue:
* `.when()`: تجبرك على تغطية الحالات الثلاث (data, error, loading).
* `.maybeWhen()`: تتيح لك التعامل مع حالات محددة وتوفير `orElse`.
* `.whenData()`: مفيدة جداً إذا كنت تريد تنفيذ شيء أو عرض البيانات فقط إذا كانت موجودة، وتجاهل الـ Loading والـ Error مؤقتاً.

---

## 3. أمثلة أكواد برمجية نظيفة (Clean Code Examples)

دعنا نبني مثالاً عملياً متكاملاً يتضمن:
1. جلب قائمة منتجات (Products).
2. تطبيق ميزة **Pull-to-Refresh**.
3. التعامل مع **Pagination** (التحميل عند التمرير للأسفل).

### الخطوة الأولى: الـ Provider لجلب البيانات
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

// نموذج البيانات
class Product {
  final int id;
  final String title;
  Product({required this.id, required this.title});
}

// Service وهمية لجلب البيانات
class ProductsService {
  Future<List<Product>> fetchProducts({int page = 1}) async {
    await Future.delayed(const Duration(seconds: 2)); // محاكاة تأخير الشبكة
    if (page == 3) throw Exception('فشل الاتصال بالخادم!');
    
    return List.generate(
      10, 
      (index) => Product(id: (page - 1) * 10 + index, title: 'منتج رقم ${(page - 1) * 10 + index}')
    );
  }
}

final productsServiceProvider = Provider((ref) => ProductsService());

// استخدام AsyncNotifier لإدارة حالة الـ Pagination والـ Refresh
final productsProvider = AsyncNotifierProvider<ProductsNotifier, List<Product>>(() {
  return ProductsNotifier();
});

class ProductsNotifier extends AsyncNotifier<List<Product>> {
  int _page = 1;
  bool _hasMore = true;

  bool get hasMore => _hasMore;

  @override
  Future<List<Product>> build() async {
    _page = 1;
    _hasMore = true;
    return ref.read(productsServiceProvider).fetchProducts(page: _page);
  }

  // دالة الـ Pull-to-Refresh
  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => build());
  }

  // دالة الـ Pagination (تحميل المزيد)
  Future<void> loadMore() async {
    // إذا كان هناك تحميل حالي أو نفذت البيانات، لا تقم بشيء
    if (state.isLoading || !_hasMore) return;

    // نحتفظ بالبيانات القديمة ونضع الحالة على أنها loading مع الاحتفاظ بالبيانات (isLoadingPrevious)
    final oldData = state.value ?? [];
    state = AsyncValue.data(oldData); // أو نحافظ على الـ loading المدمج

    try {
      _page++;
      final newData = await ref.read(productsServiceProvider).fetchProducts(page: _page);
      
      if (newData.isEmpty) {
        _hasMore = false;
      }

      state = AsyncValue.data([...oldData, ...newData]);
    } catch (e, st) {
      // في حال حدث خطأ في الصفحة التالية، لا نفسد البيانات القديمة، بل نكتفي بإظهار SnackBar مثلاً
      // أو نمرر الخطأ بحسب متطلبات التصميم
    }
  }
}
```

### الخطوة الثانية: واجهة المستخدم (UI) مع Pull-to-Refresh و Pagination
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod ConsumerWidget';

class ProductsScreen extends ConsumerStatefulWidget {
  const ProductsScreen({super.key});

  @override
  ConsumerState<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends ConsumerState<ProductsScreen> {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      ref.read(productsProvider.notifier).loadMore();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // مراقبة الـ Provider
    final productsAsync = ref.watch(productsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('متجر CodeU - المنتجات')),
      body: productsAsync.when(
        // 1. حالة التحميل الأولي
        loading: () => const Center(child: CircularProgressIndicator()),
        
        // 2. حالة الخطأ
        error: (error, stackTrace) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('حدث خطأ: ${error.toString()}'),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.read(productsProvider.notifier).refresh(),
                child: const Text('إعادة المحاولة'),
              ),
            ],
          ),
        ),
        
        // 3. حالة النجاح (Data)
        data: (products) {
          return RefreshIndicator(
            onRefresh: () => ref.read(productsProvider.notifier).refresh(),
            child: ListView.builder(
              controller: _scrollController,
              itemCount: products.length + (ref.read(productsProvider.notifier).hasMore ? 1 : 0),
              itemBuilder: (context, index) {
                if (index < products.length) {
                  final product = products[index];
                  return ListTile(
                    leading: CircleAvatar(child: Text(product.id.toString())),
                    title: Text(product.title),
                  );
                } else {
                  // مؤشر تحميل في أسفل القائمة أثناء جلب صفحة جديدة
                  return const Padding(
                    padding: EdgeInsets.all(16.0),
                    center: Center(child: CircularProgressIndicator()),
                  );
                }
              },
            ),
          );
        },
      ),
    );
  }
}
```

---

## 4. أخطاء شائع وكيفية تفاديها (Common Pitfalls & Best Practices)

### ❌ الخطأ الأول: تجاهل البيانات القديمة أثناء الـ Refresh
**المشكلة:** عندما يقوم المستخدم بالسحب لتحديث الصفحة (Pull-to-refresh)، يقوم المبرمج بكتابة `state = const AsyncValue.loading()`، مما يؤدي إلى اختفاء القائمة بالكامل وظهور شاشة تحميل مزعجة تقتل تجربة المستخدم (UX).
**✅ الحل:** استخدام `AsyncValue.guard` مع الاحتفاظ بالبيانات السابقة عبر ميزة `isRefreshing` أو استخدام الطرق المتقدمة في الـ Notifier، أو جعل الـ UI يتعامل بذكاء بحيث يظهر شريط التحميل العلوي فقط دون مسح القائمة.

### ❌ الخطأ الثاني: نسيان التعامل مع الـ StackTrace في الـ Error
**المشكلة:** طباعة الخطأ فقط `catch (e)` وإهمال الـ `StackTrace`.
**✅ الحل:** في Riverpod، عندما تستخدم `AsyncValue.error(e, stackTrace)`، احرص دائماً على تمرير الـ StackTrace لمساعدتك في عمليات الـ Debugging عبر أدوات مثل Sentry أو Firebase Crashlytics.

### ❌ الخطأ الثالث: عدم استخدام `AsyncValue.guard`
**المشكلة:** كتابة `try-catch` مطولة داخل الـ Notifiers وحساب الـ Loading والـ Error يدوياً.
**✅ الحل:** `AsyncValue.guard` تقوم بالنيابة عنك بتجربة الكبير (`Future`), وإذا نجح تضعه في `AsyncData`, وإذا فشل تلتقطه وتضعه في `AsyncError` تلقائياً!
```dart
// مثال على استخدام Guard النظيف:
state = await AsyncValue.guard(() => _repository.updateData());
```

---

## 💡 خلاصة الدرس
من خلال استخدام `AsyncValue`، أصبح بناء واجهات تعتمد على الشبكة أمراً في غاية البساطة والمنهجية. في الدرس القادم [3.3] سنتعمق أكثر في **Family & AutoDispose** لنعرف كيف نمرر باراميترات للـ Providers ونقوم بتنظيف الذاكرة باحترافية. 

حافظ على شغفك، ونلتقي في قمة البرمجة مع **CodeU**! 🎓🔥