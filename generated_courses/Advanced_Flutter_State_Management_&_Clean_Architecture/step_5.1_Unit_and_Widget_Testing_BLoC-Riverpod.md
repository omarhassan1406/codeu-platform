# Testing and Production Readiness
## Unit and Widget Testing BLoC/Riverpod

أهلاً بك أيها المطور المحترف في منصة **CodeU**. معك الأستاذ الذكي، وموعدنا اليوم مع قمة الهرم البرمجي في تطوير تطبيقات الفلاتر: **اختبارات الوحدات والودجت (Unit & Widget Testing) لـ BLoC و Riverpod**.

الفرق بين المبرمج الهاوي والمحترف ليس في كتابة الكود الذي يعمل فحسب، بل في كتابة كود **قابل للاختبار (Testable)** وموثوق بنسبة 100%. في هذا الدرس العميق، سنغوص في كيفية كتابة Unit Tests لاحتياجagi الـ Business Logic (Cubit/UseCases) باستخدام مكتبة `mocktail` الحديثة، وكيفية اختبار تفاعل الودجت وتغيرات الحالة (Widget Reactivity).

---

# [5.1] Unit and Widget Testing BLoC/Riverpod

## 1. المقدمة (Introduction)
لماذا نكتب الاختبارات؟ لأن التغيير قادم لا محالة في عالم البرمجيات. عندما تقوم بتحديث مكتبة أو تعديل ميزة، كيف تضمن أن باقي التطبيق لم ينهار؟
* **Unit Testing:** يختبر أصغر وحدة كود بمعزل عن البقية (مثل: UseCase, Cubit, Repository).
* **Widget Testing:** يختبر واجهة المستخدم (UI) وتفاعل الودجت مع تغير الحالات (State Changes) دون الحاجة لتشغيل محاكي حقيقي (Simulator).

في هندسة **Clean Architecture**، فصل الـ Business Logic يجعل كتابة هذه الاختبارات أمراً ممتعاً وسهلاً للغاية إذا تم بطريقة صحيحة.

---

## 2. الشرح العميق (Deep Dive)

### أ. اختبار Cubit و UseCases باستخدام Mocktail
مكتبة `mocktail` هي البديل الحديث لـ `mockito`؛ فهي لا تتطلب توليد ملفات (Code Generation باستخدام `build_runner`)، مما يجعلها أسرع وأسهل بكثير في الاستخدام مع Dart.

* **طريقة عمل Mocktail:**
  1. نقوم بإنشاء Mock للكلاسات الخارجية (مثل Repositories).
  2. نحدد السلوك المتوقع للـ Mock باستخدام `when(() => ...).thenAnswer(...)`.
  3. نستدعي الدالة ونتحقق من النتائج أو الحالات المتصدرة باستخدام `blocTest` (لمنصة BLoC) أو التحقق المباشر (لـ UseCases).

### ب. اختبار الودجت وتغيرات الحالة (Widget Reactivity)
 لاختبار تفاعل الودجت (سواء كان يعتمد على BLoC أو Riverpod)، سنستخدم `WidgetTester`. الأداة السحرية هنا هي محاكاة ضغطات الأزرار، والتحقق من ظهور عناصر معينة أو اختفائها بناءً على الـ State.

---

## 3. أمثلة أكواد برمجية نظيفة (Clean Code Examples)

### المثال الأول: Unit Test لـ UseCase و Cubit باستخدام Mocktail (BLoC Example)

تخيل أن لدينا `GetUserDataUseCase` يعتمد على `UserRepository`، و `UserCubit` يستدعي هذا الـ UseCase.

#### 1. كود الـ UseCase والـ Cubit (للتذكرة):
```dart
class GetUserDataUseCase {
  final UserRepository repository;
  GetUserDataUseCase(this.repository);

  Future<User> call() async => await repository.getUser();
}

class UserCubit extends Cubit<UserState> {
  final GetUserDataUseCase getUserData;
  UserCubit(this.getUserData) : super(UserInitial());

  Future<void> fetchUser() async {
    emit(UserLoading());
    try {
      final user = await getUserData();
      emit(UserLoaded(user));
    } catch (e) {
      emit(UserError(e.toString()));
    }
  }
}
```

#### 2. كتابة الـ Unit Test باستخدام `mocktail` و `bloc_test`:
```dart
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

// 1. إنشاء Mock للـ UseCase أو Repository
class MockGetUserDataUseCase extends Mock implements GetUserDataUseCase {}

void main() {
  late MockGetUserDataUseCase mockUseCase;
  late UserCubit userCubit;

  setUp(() {
    mockUseCase = MockGetUserDataUseCase();
    userCubit = UserCubit(mockUseCase);
  });

  tearDown(() {
    userCubit.close();
  });

  group('UserCubit Tests', () {
    final tUser = User(id: '1', name: 'CodeU Master');

    test('initial state should be UserInitial', () {
      expect(userCubit.state, equals(UserInitial()));
    });

    // استخدام blocTest لاختبار تدفق الحالات (States Stream)
    blocTest<UserCubit, UserState>(
      'emits [UserLoading, UserLoaded] when fetchUser is successful',
      build: () {
        when(() => mockUseCase()).thenAnswer((_) async => tUser);
        return userCubit;
      },
      act: (cubit) => cubit.fetchUser(),
      expect: () => [
        UserLoading(),
        UserLoaded(tUser),
      ],
    );

    blocTest<UserCubit, UserState>(
      'emits [UserLoading, UserError] when fetchUser fails',
      build: () {
        when(() => mockUseCase()).thenThrow(Exception('Failed to fetch'));
        return userCubit;
      },
      act: (cubit) => cubit.fetchUser(),
      expect: () => [
        UserLoading(),
        isA<UserError>(),
      ],
    );
  });
}
```

---

### المثال الثاني: Widget Test مع Riverpod

إذا كان تطبيقك مبنياً بـ `Riverpod`، فإن اختبار الودجت يتم عبر تغليف الودجت بـ `ProviderScope` وإلغاء (Override) المزودات الحقيقية بمزودات وهمية (Mocks).

#### 1. الودجت المراد اختبارها:
```dart
class UserProfileView extends ConsumerWidget {
  const UserProfileView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(userProvider);

    return Scaffold(
      body: userAsync.when(
        data: (user) => Text('Welcome ${user.name}'),
        loading: () => const CircularProgressIndicator(),
        error: (e, _) => const Text('Error loading user'),
      ),
    );
  }
}
```

#### 2. كتابة الـ Widget Test:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  testWidgets('UserProfileView shows loading then data', (tester) async {
    // بناء الودجت داخل ProviderScope مع عمل Override للـ Provider
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          userProvider.overrideWith((ref) async => User(id: '1', name: 'CodeU Student')),
        ],
        const MaterialApp(home: UserProfileView()),
      ),
    );

    // في البداية يجب أن نرى مؤشر التحميل (إذا كان المستقبل غير مكتمل فوراً)
    // أو نتحقق مباشرة من ظهور البيانات لو كانت الحالة جاهزة
    await tester.pumpAndSettle(); // الانتظار حتى انتهاء الـ Async gaps

    // التحقق من ظهور اسم المستخدم
    expect(find.text('Welcome CodeU Student'), findsOneWidget);
  });
}
```

---

## 4. الأخطاء الشائعة وكيفية تفاديها (Common Pitfalls & Best Practices)

1. **نسيان استدعاء `pumpAndSettle()` أو `pump()`:**
   * *الخطأ:* محاولة البحث عن عنصر في الـ UI قبل أن يتم رسمه.
   * *الحل:* استخدم `await tester.pumpAndSettle()` بعد الأحداث (مثل الضغط على زر) لضمان انتهاء كافة الـ Animations والـ Microtasks.

2. **عدم إغلاق الـ Cubit أو الـ Stream:**
   * *الخطأ:* ترك الـ Cubit يعمل في الذاكرة بعد انتهاء الاختبار مما يسبب تداخل البيانات.
   * *الحل:* استخدم دائماً دالة `tearDown(() => cubit.close());`.

3. **إساءة استخدام `any()` في Mocktail:**
   * *الخطأ:* تمرير قيم حقيقية مع `any()` دون تسجيل الكلاس (`registerFallbackValue`) إذا كانت كلاسات مخصصة.
   * *الحل:* إذا كانت البارامترات تمرر كائنات مخصصة، تأكد من تسجيلها في دالة `setUpAll`:
     ```dart
     setUpAll(() {
       registerFallbackValue(UserParametersFake());
     });
     ```

4. **ربط الاختبارات بقاعدة بيانات حقيقية أو شبكة (Network):**
   * *الخطأ:* إجراء طلب HTTP حقيقي داخل الـ Unit Test.
   * *الحل:* قم دائماً بعمل Mock لكل الـ Data Sources والـ Repositories الخارجية لضمان سرعة الاختبارات واستقلاليتها.

---

### ملخص الدرس من CodeU 🚀
الاختبارات ليست عبئاً إضافياً، بل هي **درع الحماية** لتطبيقك. اليوم تعلمت كيف تختبر الـ Business Logic عبر Mocktail وتضمن تفاعل الودجت بدقة. طبق هذه الأمثلة في مشروعك القادم، وكن دائماً جاهزاً للإنتاج (Production-Ready)!

*نلتقي في الدرس القادم من الكورس المتقدم!*