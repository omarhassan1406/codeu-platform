# Testing and Production Readiness
## Dependency Injection and Error Boundaries

أهلاً بك أيها المطور المحترف في منصة **CodeU**. بصفتي أستاذك الذكي، أرحب بك في هذا الدرس المتقدم ضمن كورس **Advanced Flutter State Management & Clean Architecture**. 

اليوم سنغوص في واحد من أهم أعمدة هندسة البرمجيات القابلة للتوسع والصيانة: **Dependency Injection (حقن التبعيات)** باستخدام `GetIt`، وكيفية بناء **Error Boundaries (حدود معالجة الأخطاء)** لضمان استقرار التطبيق في بيئة الإنتاج (Production).

---

# الدرس [5.2]: Dependency Injection and Error Boundaries

## 1. المقدمة (Introduction)

في التطبيقات الضخمة، إدارة إنشاء الكائنات (Object Creation) وتمريرها يدويًا عبر طبقات الـ Clean Architecture (Data -> Domain -> Presentation) تصبح كابوسًا صيانةً واختباراً. هنا يأتي دور **Dependency Injection (DI)** لفصل مسؤولية إنشاء الكائنات عن استخدامها.

بالتوازي مع ذلك، حتى مع أفضل هندسة، قد تحدث أخطاء غير متوقعة (Uncaught Exceptions). ترك التطبيق ينهار (Crash) أمام المستخدم أمر غير مقبول مهنياً؛ لذا سنتعلم كيف نبني **Global Error Boundaries** لالتقاط الأخطاء، تسجيلها عبر نظام Logging احترافي، وإظهار واجهة بديلة (Fallback UI) للمستخدم.

---

## 2. الشرح العميق (Deep Dive)

### أ. نظام حقن التبعيات باستخدام `GetIt`
`GetIt` هو Service Locator خفيف الوزن وسريع في Flutter. بدلاً من تمرير `ApiClient` عبر 5 مستويات من الـ Constructors، نقوم بتسجيله في حاوية مركزية (Container) ونطلبه عند الحاجة.

أنواع التسجيل في `GetIt`:
1. **LazySingleton**: لا يتم إنشاء النسخة إلا عند طلبها أول مرة، وتظل نفس النسخة طوال دورة حياة التطبيق.
2. **Factory**: يتم إنشاء نسخة جديدة في كل مرة يتم فيها طلب الـ Dependency (مفيد جداً للـ BLoCs أو ViewModels).
3. **Singleton**: يتم إنشاء النسخة فوراً عند التسجيل.

### ب. حدود الأخطاء (Error Boundaries) والـ Logging
في Flutter، الـ `FlutterError.onError` يلتقط الأخطاء التي تحدث داخل شجرة الواجهات (Widget tree)، بينما `PlatformDispatcher.instance.onError` يلتقط الأخطاء غير المُعالجة في الـ Asynchronous code والـ Isolates. سنقوم بدمجها معاً لتخزين وتقارير الأخطاء (Crashlytics مثلاً).

---

## 3. أمثلة أكواد برمجية نظيفة (Clean Code Implementation)

### الخطوة 1: إعداد ملف الـ Dependency Injection
سنقوم بإنشاء ملف `injection_container.dart` لإدارة كل التبعيات وفق مبادئ Clean Architecture.

```dart
// lib/injection_container.dart
import 'package:get_it/get_it.dart';
import 'http/http_client.dart'; // افترض وجوده
import 'features/data/datasources/user_remote_data_source.dart';
import 'features/data/repositories/user_repository_impl.dart';
import 'features/domain/repositories/user_repository.dart';
import 'features/domain/usecases/get_user.dart';
import 'features/presentation/bloc/user_bloc.dart';

final sl = GetIt.instance;

Future<void> initDependencies() async {
  // 1. External & Core
  // تسجيل HttpClient كـ Singleton
  sl.registerLazySingleton<HttpClient>(() => HttpClientImpl());

  // 2. Data Sources
  sl.registerLazySingleton<UserRemoteDataSource>(
    () => UserRemoteDataSourceImpl(client: sl()),
  );

  // 3. Repositories
  sl.registerLazySingleton<UserRepository>(
    () => UserRepositoryImpl(remoteDataSource: sl()),
  );

  // 4. Use Cases
  sl.registerLazySingleton(() => GetUser(sl()));

  // 5. Presentation / BLoC
  // ملاحظة: نستخدم Factory للـ BLoC لضمان حصول كل شاشة على نسخة نظيفة
  sl.registerFactory(() => UserBloc(getUser: sl()));
}
```

---

### الخطوة 2: تطبيق Global Error Boundary & Logger
سنقوم بإنشاء طبقة معالجة أخطاء عامة وتسجيلها في نقطة بداية التطبيق `main.dart`.

```dart
// lib/core/errors/app_error_boundary.dart
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class AppErrorBoundary {
  static void initialize() {
    // التقاط أخطاء الـ Widgets
    FlutterError.onError = (FlutterErrorDetails details) {
      FlutterError.presentError(details);
      _logError(details.exception, details.stack);
    };

    // التقاط الأخطاء غير المعالجة في الـ Dart Zone (Asynchronous)
    PlatformDispatcher.instance.onError = (error, stack) {
      _logError(error, stack);
      return true; // تعني أننا عالجنا الخطأ ولن ينهار التطبيق تماماً
    };
  }

  static void _logError(Object error, StackTrace? stackTrace) {
    // هنا يمكنك ربط النظام بـ Firebase Crashlytics أو Sentry
    debug.print('--- CRITICAL ERROR LOG ---');
    debug.print('Error: $error');
    debug.print('StackTrace: $stackTrace');
    debug.print('--------------------------');
  }
}

// شاشة بديلة تظهر في حال حدوث خطأ كارثي في واجهة المستخدم
class GlobalErrorWidget extends StatelessWidget {
  final String errorMessage;

  const GlobalErrorWidget({Key? key, required this.errorMessage}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        backgroundColor: Colors.red[50],
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, color: Colors.red, size: 80),
                const SizedBox(height: 16),
                const Text(
                  'عذراً، حدث خطأ غير متوقع!',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.red),
                ),
                const SizedBox(height: 8),
                Text(
                  errorMessage,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.grey),
                ),
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: () {
                    // إعادة تشغيل التطبيق أو العودة للرئيسية
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('إعادة المحاولة'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

---

### الخطوة 3: ربط الكل في `main.dart`

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'injection_container.dart' as di;
import 'core/errors/app_error_boundary.dart';

void main() async {
  // ضمان تهيئة بيئة الفلاتر
  WidgetsFlutterBinding.ensureInitialized();

  // تفعيل حدود الأخطاء
  AppErrorBoundary.initialize();

  // تهيئة الـ Dependency Injection
  await di.initDependencies();

  // تخصيص شكل الـ ErrorWidget الافتراضي في وضع الـ Release
  ErrorWidget.builder = (FlutterErrorDetails details) {
    return GlobalErrorWidget(errorMessage: details.exception.toString());
  };

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CodeU Clean Architecture',
      theme: ThemeData(primarySwatch: Colors.blue),
      home: const Scaffold(
        body: Center(child: Text('Welcome to CodeU Advanced Flutter!')),
      ),
    );
  }
}
```

---

## 4. الأخطاء الشائعة وكيفية تفاديها (Common Pitfalls & Best Practices)

### ❌ الخطأ الأول: تسجيل الـ BLoC أو ViewModel كـ Singleton
* **المشكلة:** إذا قمت بتسجيل `Bloc` باستخدام `sl.registerLazySingleton<MyBloc>()`، فإن التطبيق سيحتفظ بنفس الحالة (State) والبيانات القديمة كلما انتقلت للشاشة ورجعت إليها.
* **الحل:** دائماً استخدم `sl.registerFactory<MyBloc>(() => MyBloc(...))` للـ ViewModels أو الـ BLoCs لضمان تدميرها وإنشاء نسخة جديدة نظيفة عند الخروج والدخول للشاشة.

### ❌ الخطأ الثاني: نسيان ترتيب الـ Dependencies
* **المشكلة:** محاولة حقن `Repository` يعتمد على `DataSource`، لكنك قمت بتسجيل الـ Repository *قبل* الـ DataSource في ملف `GetIt`. سيؤدي هذا إلى `ArgumentError` وقت التشغيل.
* **الحل:** دائماً ابدأ بتسجيل الطبقات الدنيا (External / Core -> DataSources -> Repositories -> UseCases -> Presentation).

### ❌ الخطأ الثالث: تجاهل الأخطاء غير المتزامنة (Async Exceptions)
* **المشكلة:** الاعتماد فقط على `try-catch` داخل الـ UI والـ BLoC، وترك الأخطاء التي تحدث داخل الـ Streams أو Futures المعزولة تمر بدون التقاط.
* **الحل:** استخدم دائماً `PlatformDispatcher.instance.onError` لضمان عدم انهيار التطبيق صامتاً في خلفية الجهاز.

---

### 💡 ملخص الدرس من أستاذ CodeU:
الـ Dependency Injection يمنحك كودًا مرنًا وسهل الاختبار (Unit & Widget Testing)، بينما الـ Error Boundaries تمنح مستخدمك تجربة مستقرة خالية من الانهيارات المفاجئة. طبق هذه الأنماط بدقة، ونلتقي في الدرس القادم حيث سنكتب أول اختبارات حقيقية لتطبيقنا!