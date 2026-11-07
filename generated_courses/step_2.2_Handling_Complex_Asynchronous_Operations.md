# Advanced BLoC and Cubit Patterns
## Handling Complex Asynchronous Operations

أهلاً بك أيها المطور المحترف في منصة **CodeU**. معك الأستاذ الذكي، ومرافقك في رحلة إتقان هندسة البرمجيات المتقدمة. 

نستكمل اليوم رحلتنا في كورس **Advanced Flutter State Management & Clean Architecture**، وفي هذا القسم المتقدم **Advanced BLoC and Cubit Patterns**، سنتناول درساً حيويّاً يفرق بين المطور الهاوي والمطور المحترف: **[2.2] التعامل مع العمليات غير المتزامنة المعقدة (Handling Complex Asynchronous Operations)**.

---

# [2.2] Handling Complex Asynchronous Operations

## 🎯 أهداف الدرس
بانتهاء هذا الدرس، ستكون قادراً على:
1. تطبيق تقنيات **Debouncing** و **Throttling** داخل الـ BLoC للتحكم في تدفق الأحداث (Events).
2. إدارة الطلبات المتزامنة والمتقاطعة (Concurrent Requests) وتجنب السباق البرمجي (Race Conditions).
3. بناء استراتيجية متكاملة للتعامل مع الأخطاء وإخفاقات الشبكة بشكل أنيق لا يكسر تجربة المستخدم (Graceful Error Handling).

---

## 1. مقدمة: لماذا تصبح العمليات غير المتزامنة معقدة؟
في تطبيقات الفلاتر الحقيقية، لا تعمل الأحداث بمعزل عن بعضها. المستخدم قد يكتب بسرعة في حقل بحث (مما يولد آلاف الأحداث)، أو يضغط زر "حفظ" عدة مرات متتالية (مما يرسل طلبات مكررة للخادم)، أو قد تتداخل استجابات الشبكة بحيث تصل استجابة لطلب قديم *بعد* استجابة لطلب أحدث (Race Condition).

اعتماد الطريقة التقليدية في الـ BLoC قد يؤدي إلى:
* استنزاف موارد الجهاز والشبكة (API Rate Limiting issues).
* حالات غير متوقعة في الـ UI (Inconsistent States).
* انهيار التطبيق أو ظهور رسائل خطأ مزعجة للمستخدم.

---

## 2. شرح عميق وأمثلة برمجية

### أولاً: Debouncing & Throttling باستخدام `stream_transform`
الفرق باختصار:
* **Debouncing:** ينتظر حتى يتوقف المستخدم عن إرسال الحدث لفترة زمنية محددة (مثل: التوقف عن الكتابة في شريط البحث).
* **Throttling:** يسمح بمرور حدث واحد فقط خلال فترة زمنية محددة، بغض النظر عن عدد مرات إرساله (مثل: زر الضغط للإرسال لمنع Double-clicks).

> **ملاحظة:** تأكد من إضافة حزمة `stream_transform` إلى ملف `pubspec.yaml`.

#### مثال عملي: Search BLoC مع Debouncing
```dart
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:stream_transform/stream_transform.dart';

// --- Events ---
abstract class SearchEvent {}
class SearchTextChanged extends SearchEvent {
  final String query;
  SearchTextChanged(this.query);
}

// --- States ---
abstract class SearchState {}
class SearchInitial extends SearchState {}
class SearchLoading extends SearchState {}
class SearchLoaded extends SearchState {
  final List<String> results;
  SearchLoaded(this.results);
}
class SearchError extends SearchState {
  final String message;
  SearchError(this.message);
}

// --- BLoC ---
class SearchBloc extends Bloc<SearchEvent, SearchState> {
  final SearchRepository repository;

  SearchBloc(this.repository) : super(SearchInitial()) {
    on<SearchTextChanged>(
      _onSearchTextChanged,
      transformer: _debounce(const Duration(milliseconds: 300)), // تطبيق الـ Debounce هنا
    );
  }

  // دالة مساعدة لتطبيق الـ Debounce على الـ Stream
  EventTransformer<T> _debounce<T>(Duration duration) {
    return (events, mapper) => events.debounce(duration).switchMap(mapper);
  }

  Future<void> _onSearchTextChanged(
    SearchTextChanged event,
    Emitter<SearchState> emit,
  ) async {
    if (event.query.isEmpty) {
      emit(SearchInitial());
      return;
    }

    emit(SearchLoading());

    try {
      final results = await repository.search(event.query);
      emit(SearchLoaded(results));
    } catch (e) {
      emit(SearchError('فشل البحث، تأكد من اتصالك بالإنترنت.'));
    }
  }
}
```

---

### ثانياً: إدارة الطلبات المتزامنة (Concurrent Requests & Race Conditions)
لاحظ استخدامنا لـ `switchMap` في الكود أعلاه بدلاً من `flatMap` أو `concatMap`. 
* **`switchMap`**: يقوم بإلغاء الطلب (أو تجاهل الـ Stream الناتج) السابق فور وصول حدث جديد. هذا يمنع تماماً مشاكل الـ **Race Conditions** حيث تضمن أن النتائج المعروضة دائماً تخص *آخر* طلب تم إرساله.

---

### ثالثاً: التعامل الأنيق مع الأخطاء (Graceful Error Handling)
في Clean Architecture، يجب ألا تتعامل الطبقات العليا (BLoC) مع استثناءات الشبكة الخام (Raw Exceptions) مثل `SocketException` أو `DioError` بشكل مباشر، بل يتم تحويلها إلى `Failure` objects أو رسائل مفهومة.

```dart
Future<void> _onFetchData(
  FetchDataEvent event,
  Emitter<AppState> emit,
) async {
  emit(AppLoading());
  
  final result = await repository.getData();
  
  // استخدام Either Pattern (مثل الحزمة fpdart أو dartz)
  result.fold(
    (failure) => emit(AppError(_mapFailureToMessage(failure))),
    (data) => emit(AppLoaded(data)),
  );
}

String _mapFailureToMessage(Failure failure) {
  switch (failure.runtimeType) {
    case ServerFailure:
      return 'خطأ في الخادم، يرجى المحاولة لاحقاً.';
    case NetworkFailure:
      return 'لا يوجد اتصال بالإنترنت.';
    default:
      return 'حدث خطأ غير متوقع.';
  }
}
```

---

## ⚠️ أخطاء شائعة وكيفية تفاديها

1. **الخطأ الأول: نسيان إلغاء العمليات (Memory Leaks / Unclosed Streams)**
   * *المشكلة:* إطلاق `Timer` أو الاستماع لـ Streams داخل الـ BLoC بدون إغلاقها عند انتهاء الـ BLoC.
   * *الحل:* اعتماد `EventTransformers` الخاصة بـ `bloc_concurrency` و `stream_transform` لأنها تدار تلقائياً عبر دورة حياة الـ BLoC.

2. **الخطأ الثاني: تجاهل الـ Race Conditions في شاشات الـ Pagination**
   * *المشكلة:* قيام المستخدم بالسحب لأسفل بسرعة لتحديث البيانات (Pull-to-refresh) مما يرسل طلبات متداخلة تفسد الترتيب.
   * *الحل:* استخدام `droppable()` transformer لمنع استقبال أحداث جديدة حتى ينتهي الحدث الحالي من المعالجة.

3. **الخطأ الثالث: إظهار رسائل خطأ تقنية للمستخدم**
   * *المشكلة:* طباعة `DioException [Error 500]: Internal Server Error` مباشرة على واجهة المستخدم.
   * *الحل:* دائماً قم بعمل **Mapping** للاستثناءات إلى رسائل إنسانية ودودة (User-Friendly Messages).

---

## 💡 خلاصة الدرس
التحكم في العمليات غير المتزامنة هو ما يرفع جودة تطبيقك من "يعمل بشكل جيد" إلى "يعمل باحترافية وثبات تام تحت أسوأ ظروف الشبكة". استخدم `stream_transform` للتحكم بالتدفق، واعتمد `Either` أو نمط الـ Failures لإدارة الأخطاء بأمان.

في الدرس القادم [2.3]، سننتقل إلى **Testing Advanced BLoCs with Mockito & BlocTest**. كن مستعداً!