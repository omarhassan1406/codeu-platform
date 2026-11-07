# Advanced Python Concepts
## Decorators

أهلاً بك يا بطل/ة في منصة **CodeU**! 🚀 

نحن اليوم على موعد مع واحد من أكثر مفهوم بايثون قوة وأناقة: **المزخرفات (Decorators)**. هذا المفهوم سيأخذ مهاراتك البرمجية إلى المستوى الاحترافي (Advanced)، وستفهم من خلاله كيف تكتب كوداً نظيفاً (Clean Code) وقابلاً لإعادة الاستخدام دون تكرار.

---

# الكورس: Programming in Python for Beginners to Advanced
## القسم: Advanced Python Concepts
### الدرس [5.3]: Decorators

---

### 1. ربط سريع بما تم تعلمه سابقاً 🔄
في الأقسام السابقة، أتقنت الدوال (Functions)، وكيفية تمريرها كوسائط، وكيف يمكن لدالة أن تُرجع دالة أخرى (Higher-Order Functions). اليوم، سنبني على هذا الأساس لندخل عالم **Decorators**. 

المزخرف (Decorator) باختصار شديد هو "غلاف" أو "مضيف" يأخذ دالة موجودة مسبقاً، يضيف عليها سلوكاً جديداً أو يعدل أداءها، **دون أن يغير سطر واحد من كود الدالة الأصلية**.

---

### 2. الشرح العميق والمبسط 🧠

لفهم الـ Decorators، يجب أن نستوعب القاعدة الذهبية في بايثون:
> **"الدوال في بايثون هي كائنات من الدرجة الأولى (First-Class Objects)."**

هذا يعني أن الدالة يمكنها:
1. أن تُخزن في متغير.
2. أن تُتمرر كمعامل لدالة أخرى.
3. أن يتم إرجاعها من دالة أخرى.

#### كيف يعمل الـ Decorator؟
تخيل أن لديك دالة تطبع رسالة ترحيب:
```python
def say_hello():
    print("مرحباً بك في CodeU!")
```
تريد الآن أن تقيس **الوقت المستغرق** لتنفيذ هذه الدالة، أو تتأكد أن المستخدم **مسجل الدخول** قبل تنفيذها، دون تعديل دالة `say_hello` نفسها. هنا يأتي دور الـ Decorator!

#### الهيكل الأساسي للـ Decorator:
```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        # 1. كود يتم تنفيذه قبل الدالة الأصلية
        print("--- بدء التنفيذ ---")
        
        result = func(*args, **kwargs)  # تنفيذ الدالة الأصلية
        
        # 2. كود يتم تنفيذه بعد الدالة الأصلية
        print("--- انتهاء التنفيذ ---")
        
        return result
    return wrapper
```

#### استخدام `functools.wraps` للحفاظ على البيانات الوصفية (Metadata):
عندما نغلف دالة بأخرى، فإن الدالة الأصلية تفقد اسمها (`__name__`) ومستندها (`__doc__`) ويصبح اسمها `wrapper`. لحل هذه المشكلة واحتراف كتابة الكود، نستخدم مكتبة `functools`:

```python
from functools import wraps

def my_decorator(func):
    @wraps(func)  # هذا يحافظ على اسم ومستند الدالة الأصلية
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

---

### 3. أمثلة أكواد برمجية نظيفة (تطبيق حقيقي) 💻

دعنا نكتب تطبيقاً حقيقياً: **مراقبة الأداء (Performance Monitor Decorator)** لقياس الزمن الذي تستغرقه أي دالة لتنفيذ مهمتها.

```python
import time
from functools import wraps

# 1. كتابة الـ Decorator
def measure_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # بدء العداد
        
        result = func(*args, **kwargs)  # تشغيل الدالة المستهدفة
        
        end_time = time.time()    # انتهاء العداد
        execution_time = end_time - start_time
        
        print(f"⏱️ الدالة [{func.__name__}] استغرقت {execution_time:.6f} ثانية لتنفيذها.")
        return result
    
    return wrapper

# 2. استخدام الـ Decorator مع @ syntax الجميل
@measure_time
def heavy_calculation(n):
    """دالة تقوم بحسابات ثقيلة محاكاةً"""
    total = 0
    for i in range(n):
        total += i
    return total

# 3. التجربة والاستخدام
if __name__ == "__main__":
    print(f"اسم الدالة المحفوظ: {heavy_calculation.__name__}")
    print(f"مستند الدالة: {heavy_calculation.__doc__}")
    print("-" * 40)
    
    # تشغيل الدالة
    result = heavy_calculation(10_000_000)
    print(f"النتيجة النهائية: {result}")
```

---

### 4. تمرين عملي يمهد للخطوة القادمة 🏋️‍♂️

لترسيخ ما تعلمته، قم بحل التمرين التالي قبل الانتقال للدرس القادم:

**مهمتك:**
اكتب Decorator باسم `require_permission` يقوم بالآتي:
1. يفترض أن لديك متغيراً يمثل دور المستخدم (مثلاً: `user_role = "guest"` أو `"admin"`).
2. الـ Decorator يجب أن يتحقق مما إذا كان `user_role == "admin"`.
3. إذا كان مديراً، يتم تنفيذ الدالة بنجاح.
4. إذا لم يكن كذلك، يطبع رسالة خطأ مثل: `"❌ عذراً، ليس لديك صلاحية للوصول!"` ولا يفلح في تنفيذ الدالة.
5. لا تنسَ استخدام `@wraps`.

**تمهيد للخطوة القادمة:** في الدرس القادم، سنتعمق أكثر ونرى كيف نقوم بإنشاء **Decorators تستقبل معاملات (Decorators with Arguments)** وكيف نستخدم عدة Decorators على نفس الدالة! 

بالتوفيق، ونراكم في منصة **CodeU**! 🌟