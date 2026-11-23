# Clean Architecture in Flutter
## Layers of Clean Architecture

# الأستاذ الذكي من CodeU: رحلتك لاحتراف هندسة البرمجيات

أهلاً بك يا بطل/ة في منصة **CodeU**. أنا أستاذك الذكي، وسأرافقك خطوة بخطوة في رحلة تحويلك من مطور عادي إلى مهندس برمجيات (Software Engineer) حقيقي. 

اليوم، سنخوض معاً أحد أهم دروس الكورس الأقوى: **Advanced Flutter State Management & Clean Architecture**. 
درسنا اليوم هو **[4.1] Layers of Clean Architecture**.

---

## 🎯 أهداف الدرس (Learning Objectives)
ببنهاية هذا الدرس، ستكون قادراً على:
1. الفهم العميق لطبقات العمارة النظيفة الثلاث: **Domain**, **Data**, و **Presentation**.
2. تطبيق واستيعاب **قاعدة الاعتمادية (Dependency Rule)** ومنع تسريب التبعيات بين الطبقات.
3. كتابة كود مهيكل، قابل للاختبار (Testable)، وقابل للصيانة (Maintainable).

---

## 🏗️ مقدمة: لماذا Clean Architecture؟

تخيل أنك تنشئ تطبيقاً ينمو كل يوم. بعد 6 أشهر، أصبحت إضافة ميزة جديدة كابوساً، وتغيير قاعدة البيانات (من Hive إلى Isar مثلاً) يتطلب إعادة كتابة نصف التطبيق! السبب؟ كود غير منظّم ومترابط بشدة (Tightly Coupled).

**Clean Architecture** (التي وضع قواعدها روبرت مارتن - Uncle Bob) تحل هذه المشكلة تماماً عن طريق فصل اهتمامات التطبيق (Separation of Concerns) إلى طبقات مستقلة، بحيث تعتمد الطبقات الداخلية على نفسها فقط، وتتجه التبعيات دائماً نحو الداخل (إلى Domain).

---

## 🔍 الشرح العميق: طبقات العمارة النظيفة (The Three Layers)

تتكون العمارة النظيفة في تطبيقات Flutter من 3 طبقات رئيسية، محاطة ببعضها كحلقات البصل:

```text
 ┌────────────────────────────────────────────────────────┐
 │ Presentation Layer (UI, ViewModels / Bloc)             │
 │  ┌───────────────────────────────────────────────────┐ │
 │  │ Data Layer (Models, Repositories Impl, Datasources│ │
 │  │  ┌─────────────────────────────────────────────┐  │ │
 │  │  │ Domain Layer (Entities, UseCases, Repos)    │  │ │
 │  │  └─────────────────────────────────────────────┘  │ │
 │  └───────────────────────────────────────────────────┘ │
 └────────────────────────────────────────────────────────┘
```

### 1. طبقة النطاق (Domain Layer) - قلب التطبيق 🫀
* **ما هي؟** هي الطبقة الأهم والأكثر نقاءً في تطبيقك. تحتوي على منطق الأعمال الخالص (Business Logic).
* **هل تعلم؟** هذه الطبقة **لا تعرف شيئاً** عن Flutter، ولا عن قاعدة بيانات، ولا عن مكتبات خارجية (مثل `http` أو `bloc`). هي كود Dart خالص (Pure Dart).
* **مكوناتها الرئيسية:**
  * **Entities:** الكائنات الأساسية التي تمثل نموذج الأعمال (مثل `User`, `Product`).
  * **Use Cases (Interactors):** تمثل عملية واحدة يقوم بها المستخدم (مثل `LoginUser`, `GetCartItems`). كل UseCase يمثل ميزة (Feature) منفردة.
  * **Repositories (Interfaces):** عقود (Abstract Classes) تحدد ما يمكن فعله، دون معرفة كيف يتم تنفيذه.

### 2. طبقة البيانات (Data Layer) - المزوّد والمخزن 📦
* **ما هي؟** الطبقة المسؤولة عن جلب البيانات وتخزينها، سواء من الإنترنت (API)، أو قاعدة بيانات محلية (Local DB)، أو ذاكرة مؤقتة (Cache).
* **مكوناتها الرئيسية:**
  * **Models:** امتداد لـ Entities ولكنها مخصصة للتعامل مع مصادر البيانات (تحتوي على `fromJson` و `toJson`).
  * **Data Sources:** مصادر البيانات الخام (RemoteDataSource, LocalDataSource).
  * **Repositories Implementation:** التطبيق الفعلي للعقود (Repositories) الموجودة في طبقة الـ Domain. هنا يتم دمج مصادر البيانات.

### 3. طبقة العرض (Presentation Layer) - الواجهة والتحكم 🎨
* **ما هي؟** الطبقة التي يراها المستخدم ويتفاعل معها.
* **مكوناتها الرئيسية:**
  * **UI:** الشاشات (Screens)، Widgets، والـ Design System.
  * **State Management:** (مثل Bloc, Riverpod, Provider) تدير حالة الواجهة وتستدعي Use Cases وتستجيب للنتائج.

---

## 🧱 قاعدة الاعتمادية الحديدية (The Dependency Rule)

> **القاعدة الذهبية:** مصدر الاعتمادية يجب أن يتجه دائماً **إلى الداخل فقط** (Towards the Domain).

* **Domain** لا يعتمد على أي شيء (نقي 100%).
* **Data** تعتمد على **Domain** (تنفذ الـ Interfaces الخاصة به).
* **Presentation** تعتمد على **Domain** (تستدعي Use Cases وتستخدم Entities).
* **الممنوعات:** طبقة الـ Domain ممنوع أن تستورد شيئاً من Data أو Presentation!

---

## 💻 أمثلة أكواد برمجية نظيفة (Clean Code Implementation)

دعنا نطبق مثالاً عملياً لـ **الحصول على بيانات المستخدم (Get User Profile)**:

### 1. Domain Layer (Pure Dart)
```dart
// 1. Entity
class User {
  final String id;
  final String name;
  const User({required this.id, required this.name});
}

// 2. Repository Interface (Contract)
abstract class UserRepository {
  Future<User> getUserProfile(String userId);
}

// 3. Use Case
class GetUserProfileUseCase {
  final UserRepository repository;
  GetUserProfileUseCase(this.repository);

  Future<User> call(String userId) async {
    return await repository.getUserProfile(userId);
  }
}
```

### 2. Data Layer
```dart
// 1. Model (extends Entity & adds JSON parsing)
class UserModel extends User {
  const UserModel({required String id, required String name}) : super(id: id, name: name);

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'],
      name: json['name'],
    );
  }
}

// 2. Data Source
abstract class UserRemoteDataSource {
  Future<UserModel> fetchUserData(String userId);
}

// 3. Repository Implementation
class UserRepositoryImpl implements UserRepository {
  final UserRemoteDataSource remoteDataSource;

  UserRepositoryImpl(this.remoteDataSource);

  @override
  Future<User> getUserProfile(String userId) async {
    // هنا يتم جلب Model وتحويله لـ Entity (إن لزم) أو إرجاعه مباشرة لأنه يورث منه
    final userModel = await remoteDataSource.fetchUserData(userId);
    return userModel; 
  }
}
```

### 3. Presentation Layer (Flutter + Bloc)
```dart
class UserBloc extends Bloc<UserEvent, UserState> {
  final GetUserProfileUseCase getUserProfileUseCase;

  UserBloc(this.getUserProfileUseCase) : super(UserInitial()) {
    on<FetchUserEvent>((event, emit) async {
      emit(UserLoading());
      try {
        final user = await getUserProfileUseCase(event.userId);
        emit(UserLoaded(user));
      } catch (e) {
        emit(UserError(e.toString()));
      }
    });
  }
}
```

---

## ⚠️ أخطاء شائعة وكيفية تفاديها (Common Pitfalls)

1. **الخطأ:** تمرير `UserModel` (من طبقة Data) مباشرة إلى طبقة `Presentation`.
   * **التفادي:** استخدم دائماً `Entity` في طبقة العرض والـ Domain، وقم بعمل Mapping من Model إلى Entity داخل الـ Repository Implementation.
2. **الخطأ:** وضع كود يعتمد على Flutter (مثل `BuildContext` أو `SharedPreferences`) داخل طبقة `Domain`.
   * **التفادي:** تذكر أن Domain هو كود Dart نقي. استخدم حقن الاعتماديات (Dependency Injection) عبر الـ Interfaces.
3. **الخطأ:** دمج الـ Use Case مع الـ Repository (جعل طبقة العرض تتحدث مباشرة مع Data).
   * **التفادي:** الـ Use Cases ضرورية جداً لفصل منطق العمل (Business Rules) عن طريقة العرض وعن مصدر البيانات، مما يسهل كتابة Unit Tests.

---

## 📝 الخلاصة وتحدي CodeU
اليوم تعلمنا كيف نقسم تطبيقنا إلى ثلاث طبقات (Domain, Data, Presentation) وكيف نحافظ على قاعدة الاعتمادية لتحقيق استقرار الكود.

**🔥 تحدي الدرس لك:**
قم بإنشاء ميزة جديدة في مشروعك التطبيقي (مثل "تسجيل الخروج - Logout") مطبقاً فيها الـ Clean Architecture بكل تفاصيلها (Entity, UseCase, Repository Interface & Impl, DataSource, State Management).

أنا أستاذك الذكي من CodeU، أراك في الدرس القادم **[4.2] Dependency Inversion & GetIt** لننقل هندسة برمجياتك لمستوى خارق! 🚀