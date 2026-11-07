# Riverpod Mastery
## Riverpod Providers Overview

أهلاً بك أيها المبرمج المتميز في منصة **CodeU**. بصفتي أستاذك الذكي، يسعدني أن أرافقك اليوم في رحلة عميقة ومتقدمة داخل عالم **Riverpod**، أحد أقوى وأحدث أنظمة إدارة الحالة في إطار العمل Flutter.

في هذا الدرس **[3.1] Riverpod Providers Overview**، سنقوم بتفكيك الأنواع الأساسية للمزودات (Providers)، وسنغوص في مفاهيم متقدمة تجعل تحكمك بالتطبيق احترافياً وفعالاً.

---

# 📚 المحتوى التعليمي: نظرة شاملة على Riverpod Providers

## 1. المقدمة (Introduction)
عندما ننتقل من إدارة الحالة التقليدية إلى Riverpod، فإننا ندخل عالماً يعتمد على الاعتمادية الآمنة (Type-safe dependency injection) وإدارة الحالة التفاعلية. 
في هذا الدرس، سنستكشف ثلاثة أنواع رئيسية من الـ Providers التي تُستخدم في 90% من تطبيقات Flutter الواقعية:
1. **Provider**: للقراءات الثابتة والبيانات المحسوبة.
2. **StateProvider**: لإدارة حالات بسيطة جداً (مثل عداد أو فلتر).
3. **StateNotifierProvider**: لإدارة حالات معقدة تحتوي على منطق عمل (Business Logic).

بالإضافة إلى ذلك، سنتعلم كيف ندير دورة حياة الذاكرة باستخدام **Modifiers** مثل `autoDispose` و `family`.

---

## 2. الشرح العميق (Deep Dive)

### أ. أنواع الـ Providers الأساسية

* **`Provider`**:
  * **الاستخدام:** يُستخدم لتوفير كائنات ثابتة لا تتغير قيمتها بمرور الوقت (مثل مستودعات البيانات Repositories، أو خدمات الـ API، أو قيم محسوبة بناءً على Providers أخرى).
  * **الميزة:** يتم تنفيذه مرة واحدة ولا يعيد بناء UI عبثاً.

* **`StateProvider`**:
  * **الاستخدام:** مصمم للحالات البسيطة جداً (مثل `enum` للترتيب، أو `bool` لتفعيل الوضع الليلي، أو `int` لعداد بسيط).
  * **التحذير:** لا يُنصح به إذا كانت الحالة تتطلب منطق عمل معقد (Business Logic) أو تعديلات متعددة.

* **`StateNotifierProvider`**:
  * **الاستخدام:** هو الحصان الرابح في التطبيقات الكبيرة. يتعامل مع كائن `StateNotifier` يحي版的 الحالة والمنطق معاً.
  * **الميزة:** يفصل تماماً بين واجهة المستخدم (UI) ومنطق التطبيق (Logic)، مما يتماشى تماماً مع **Clean Architecture**.

---

### ب. معدلات الأداء والموارد (Modifiers)

* **`.autoDispose`**:
  * افتراضياً، يحتفظ Riverpod بالحالة في الذاكرة طوال فترة تشغيل التطبيق. 
  * عند استخدام `autoDispose`، يقوم Riverpod تلقائياً بمسح الحالة من الذاكرة بمجرد ألا يكون هناك أي Widget تستمع (listen) لهذا الـ Provider. هذا يوفر الذاكرة بشكل هائل!

* **`.family`**:
  * يُستخدم عندما تحتاج تمرير معامل (Parameter) للـ Provider عند استدعائه (مثل `userId` لجلب بيانات مستخدم معين).
  * يتيح لك إنشاء نسخة فريدة من الـ Provider لكل معامل مختلف.

---

## 3. أمثلة أكواد برمجية نظيفة (Clean Code Examples)

دعونا نرى كيف نكتب هذه الأنواع بأسلوب احترافي يتماشى مع Clean Architecture:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

// 1. Provider عادي (ثابت / خدمة)
final apiServiceProvider = Provider<ApiService>((ref) {
  return ApiService();
});

// 2. StateProvider لحالة بسيطة (مثلاً: تفعيل الإشعارات)
final notificationsEnabledProvider = StateProvider<bool>((ref) => true);

// 3. StateNotifier لحالة معقدة (Counter Example)
class CounterNotifier extends StateNotifier<int> {
  CounterNotifier() : super(0); // القاية الابتدائية = 0

  void increment() => state++;
  void decrement() {
    if (state > 0) state--;
  }
}

final counterProvider = StateNotifierProvider<CounterNotifier, int>((ref) {
  return CounterNotifier();
});

// 4. AutoDispose & Family Provider (جلب بيانات مستخدم برقم المعرف)
final userProfileProvider = FutureProvider.autoDispose.family<User, String>((ref, userId) async {
  // نقوم بجلب الخدمة من الـ Provider الآخر
  final apiService = ref.watch(apiServiceProvider);
  return await apiService.fetchUser(userId);
});

// نماذج وهمية للتوضيح
class ApiService {
  Future<User> fetchUser(String id) async {
    await Future.delayed(const Duration(seconds: 1));
    return User(id: id, name: 'مبرمج CodeU');
  }
}

class User {
  final String id;
  final String name;
  User({required this.id, required this.name});
}
```

### كيف نستخدمها داخل الـ Widgets؟
```dart
class CounterScreen extends ConsumerWidget {
  const CounterScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // الاستماع للحالة
    final count = ref.watch(counterProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('CodeU Riverpod Masterclass')),
      body: Center(
        child: Text(
          'Counter: $count',
          style: const TextStyle(fontSize: 24),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // استدعاء الميثود بدون إعادة بناء الـ Widget بالكامل
          ref.read(counterProvider.notifier).increment();
        },
        child: const Icon(Icons.add),
      ),
    );
  }
}
```

---

## 4. أخطاء شائعة وكيفية تفاديها (Common Pitfalls & Best Practices)

### ❌ الخطأ الأول: استخدام `ref.watch` داخل الـ Callbacks والأزرار (Buttons)
* **المشكلة:** يؤدي استخدام `ref.watch` داخل الدوال مثل `onPressed` أو `initState` إلى انهيار التطبيق أو إعادة بناء غير متوقعة لأن `watch` مصممة حصرياً لدوال الـ `build()`.
* **✅ الحل:** استخدم دائماً `ref.read` داخل الأحداث والـ Callbacks.
  ```dart
  // خطأ ❌
  onPressed: () => ref.watch(counterProvider.notifier).increment();

  // صحيح ✅
  onPressed: () => ref.read(counterProvider.notifier).increment();
  ```

### ❌ الخطأ الثاني: تجاهل استخدام `autoDispose` مع البيانات الضخمة
* **المشكلة:** الاحتفاظ ببيانات صفحات تم الخروج منها في الذاكرة يؤدي إلى استهلاك عالي لـ RAM وبطء التطبيق (Memory Leaks).
* **✅ الحل:** اعتاد على إضافة `.autoDispose` لأي Provider يجلب بيانات من شبكة الإنترنت أو قاعدة بيانات مرتبطة بشاشات معينة.

### ❌ الخطأ الثالث: وضع منطق معقد داخل `StateProvider`
* **المشكلة:** `StateProvider` مصمم للقيم البسيطة. كتابة عمليات معقدة (مثل التحقق من صحة بيانات، طلبات API) تحته يجعل الكود غير قابل للصيانة.
* **✅ الحل:** عندما تتعدى الحالة مجرد رقم أو نص بسيط، انتقل فوراً إلى استخدام `StateNotifierProvider` أو `AsyncNotifierProvider`.

---

> **💡 نصيحة الأستاذ الذكي (CodeU Pro Tip):**
> "الكود النظيف ليس الذي يعمل فحسب، بل الذي يستطيع أي مبرمج آخر فهمه وتعديله بسهولة. اجعل الـ Providers الخاصة بك موزعة في ملفات منظمة تبعاً لطبقات Clean Architecture، وتذكر دائماً: **`watch` للرؤية داخل الـ UI، و `read` للفعل داخل الأحداث!**"

إلى اللقاء في الدرس القادم من منصة CodeU! 🚀