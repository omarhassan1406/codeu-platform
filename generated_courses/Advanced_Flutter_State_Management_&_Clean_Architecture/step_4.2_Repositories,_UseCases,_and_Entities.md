# Clean Architecture in Flutter
## Repositories, UseCases, and Entities

أهلاً بك أيها المطور الطموح في منصة **CodeU**، منصة بناء المطورين المحترفين. 

نستكمل اليوم رحلتنا في كورس *Advanced Flutter State Management & Clean Architecture*. في هذا الدرس **[4.2]**، سنغوص في قلب الـ Clean Architecture وتحديداً في طبقة الـ Domain وطبقة الـ Data، لنفهم كيف ندير منطق التطبيق بحكمة ونفصل البيانات عن قواعد العمل باستخدام **Entities**, **UseCases**, و **Repositories**.

---

# الدرس [4.2]: Repositories, UseCases, and Entities

## 1. مقدمة (Introduction)
في الدرس السابق، تعرفنا على هيكلية Clean Architecture وككيفية تقسيم التطبيق إلى دوائر متحدة المركز (Domain, Data, Presentation). 
اليوم، سنركز على **Domain Layer** (وهي جوهر التطبيق) وكيف تتواصل مع **Data Layer** عبر عقود واضحة. 

سنُجيب عن الأسئلة التالية:
* ما الفرق الحقيقي بين `Entity` و `Data Model`؟
* لماذا نضع منطق العمل داخل `UseCases` وليس في الـ UI أو الـ BLoC؟
* كيف نصمم `Repository Pattern` بطريقة احترافية تعتمد على تجريد الأبستراكشن (Abstraction)؟

---

## 2. الشرح العميق (Deep Dive)

### أ. الـ Entities (كيانات Domain)
الـ `Entity` هو مجرد Object يمثل مفهوم بيزنس حقيقي (مثل `User`, `Product`, `Order`). 
* **خصائصها:** نقية تماماً (Pure Dart)، لا تحتوي على أي تبعيات لمكتبات خارجية (مثل `json_serializable` أو `Firebase`), ولا تعرف شيئاً عن قواعد البيانات أو الـ APIs.

### ب. الـ Data Models (نماذج البيانات)
الـ `Model` هو شكل البيانات كما يأتي من الخارج (JSON من API أو Map من قاعدة بيانات محليّة).
* **خصائصها:** ترث غالباً من الـ `Entity` أو تحتوي على ميثودات للتحويل (مثل `fromJson` و `toJson`). وجودها محدود في **Data Layer**.

### ج. الـ Repositories (المستودعات - الواجهات والعقود)
الـ `Repository` في Domain Layer هو مجرد **Interface (Abstract Class)** يحدد *ماذا* يمكن للتطبيق أن يفعله (مثلاً: `getUser()`)، بينما التنفيذ الفعلي (`RepositoryImpl`) في Data Layer يحدد *كيف* يتم ذلك (من API أو Cache).

### د. الـ UseCases (حالات الاستخدام / منطق العمل)
الـ `UseCase` يمثل **عملية واحدة فقط** يقوم بها المستخدم في التطبيق (مثلاً: `LoginUseCase`, `GetCartItemsUseCase`). 
* **لماذا؟** لتطبيق *Single Responsibility Principle*. يصبح الكود قابلاً للقراءة، للاختبار (Unit Testing)، وإعادة الاستخدام بسهولة.

---

## 3. أمثلة الأكواد البرمجية النظيفة (Clean Code Implementation)

دعنا نبني مثالاً عملياً لـ **User Authentication (جلب بيانات مستخدم)**.

### الخطوة 1: بناء الـ Entity (Domain Layer)
```dart
// domain/entities/user.dart
class User {
  final String id;
  final String name;
  final String email;

  const User({
    required this.id,
    required this.name,
    required this.email,
  });
}
```

### الخطوة 2: تعريف Repository Interface (Domain Layer)
هنا نضع العقد فقط، دون أي تفاصيل تقنية.
```dart
// domain/repositories/user_repository.dart
import 'package:dartz/dartz.dart'; // سنستخدم Dartz لإدارة الـ Either (Success / Failure)
import '../entities/user.dart';
import '../../core/error/failures.dart';

abstract class UserRepository {
  Future<Either<Failure, User>> getUserProfile(String userId);
}
```

### الخطوة 3: بناء الـ Data Model والـ Mapping (Data Layer)
هنا نتعامل مع الـ JSON ونحول الـ Model إلى Entity باستخدام Inheritance أو Extension.
```dart
// data/models/user_model.dart
import '../../domain/entities/user.dart';

class UserModel extends User {
  const UserModel({
    required String id,
    required String name,
    required String email,
  }) : super(id: id, name: name, email: email);

  // تحويل من JSON قادم من الـ API
  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'],
      name: json['name'],
      email: json['email'],
    );
  }

  // تحويل الـ Model إلى Entity (أو يمكن جعل الـ Model يرث الـ Entity وتمرير البيانات)
  User toEntity() {
    return User(id: id, name: name, email: email);
  }
}
```

### الخطوة 4: تطبيق الـ Repository (Data Layer)
```dart
// data/repositories/user_repository_impl.dart
import 'package:dartz/dartz.dart';
import '../../core/error/failures.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/user_repository.dart';
import '../datasources/user_remote_data_source.dart';

class UserRepositoryImpl implements UserRepository {
  final UserRemoteDataSource remoteDataSource;

  UserRepositoryImpl({required this.remoteDataSource});

  @override
  Future<Either<Failure, User>> getUserProfile(String userId) async {
    try {
      // 1. جلب الـ Model من الـ Data Source
      final userModel = await remoteDataSource.getUser(userId);
      
      // 2. تحويله إلى Entity وإرجاعه داخل Right (نجاح)
      return Right(userModel.toEntity());
    } catch (e) {
      // في حال حدوث خطأ، نُرجع Failure داخل Left
      return Left(ServerFailure(e.toString()));
    }
  }
}
```

### الخطوة 5: بناء الـ UseCase (Domain Layer)
```dart
// domain/usecases/get_user_profile_usecase.dart
import 'package:dartz/dartz.dart';
import '../../core/error/failures.dart';
import '../entities/user.dart';
import '../repositories/user_repository.dart';

class GetUserProfileUseCase {
  final UserRepository repository;

  GetUserProfileUseCase(this.repository);

  // نستخدم callable class (ميثود call) لتسهيل استدعاء الـ UseCase كأنه دالة
  Future<Either<Failure, User>> call(String userId) async {
    return await repository.getUserProfile(userId);
  }
}
```

---

## 4. أخطاء شائعة وكيفية تفاديها (Common Pitfalls & How to Avoid)

1. **الخطأ:** وضع منطق الـ UI (مثل التنقل أو إظهار Snackbar) داخل الـ UseCase.
   * **الصحيح:** UseCase مسؤول فقط عن Бизнес Логика (Business Logic). الـ UI أو الـ BLoC هو من يقرر ماذا يفعل بناءً على النتيجة.
2. **الخطأ:** جعل الـ Entity يحتوي على `fromJson` و `toJson`.
   * **الصحيح:** الـ Entity يجب أن تكون مستقلة تماماً. الـ Data Model هو من يحتوي على تفاصيل تحويل الـ JSON.
3. **الخطأ:** تضخم الـ UseCase (God UseCase) ليقوم بأكثر من عملية (مثل تسجيل الدخول وجلب الإشعارات معاً).
   * **الصحيح:** طبق مبدأ *Single Responsibility*. كل مهمة مستقلة لها UseCase خاص بها.

---

## 5. خلاصة الدرس (Summary)
* الـ **Entities** هي كائنات البيزنس النقية في الـ Domain.
* الـ **Repositories** عبارة عن Interfaces تحدد شكل البيانات المطلوبة.
* الـ **UseCases** تمثل العمليات الفردية وتنفذ منطق التطبيق الأساسي.
* الفصل السليم بين هذه الطبقات يجعل تطبيقك قابل للصيانة، التوسع، والاختبار بنسبة 100%.

في الدرس القادم **[4.3]**, سنربط هذه الطبقة مع الـ Presentation Layer ونستخدم الـ BLoC لإدارة الحالة باحترافية. استعد!