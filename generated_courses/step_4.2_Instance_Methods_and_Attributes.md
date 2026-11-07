# Object-Oriented Programming (OOP)
## Instance Methods and Attributes

أهلاً بك مجدداً أيها المبرمج البارع في منصة **CodeU**! 🚀

بصفتي أستاذك الذكي، يسعدني أن أرحّب بك في إحدى أهم المحطات في رحلتنا البرمجية: **البرمجة كائنية التوجه (Object-Oriented Programming - OOP)**. 

لقد تعلمنا في الأقسام السابقة كيف نكتب الدوال (`functions`)، وننظم الكود باستخدام المتغيرات والبيانات الأساسية. اليوم، سنرتقي بمستوى التفكير البرمجي لدينا لننتقل من مجرد كتابة الأوامر إلى **نمذجة العالم الحقيقي** عبر بناء كائنات (Objects) ذكية ومستقلة.

---

# الدرس [4.2]: Instance Methods and Attributes

## 1. ربط سريع بما تم تعلمه سابقاً 🔗
في البرمجة التقليدية (Procedural Programming)، كنا نفصل البيانات (Data) عن الوظائف التي تعالجها (Functions). كنا نمرر القوائم والقواميس إلى الدوال مراراً وتكراراً. 
لكن في **OOP**، سنقوم بدمج **البيانات** (Attributes) و**الوظائف** (Methods) معاً داخل صندوق سحري واحد يسمى **الفئة (Class)**، لإنتاج كائنات (Instances/Objects) تحمل خصائص وتقوم بسلوكيات تخصها وحدها.

---

## 2. الشرح العميق والمبسط 🧠

### أ. ما هي الفئة (Class) والكائن (Instance)؟
* **الـ Class:** هو "المخطط الهندسي" أو "القالب" (مثل مخطط بناء منزل).
* **الـ Instance (الكائن):** هو "المنزل الحقيقي" الذي تم بناءه بناءً على هذا المخطط. يمكنك بناء ألف منزل من نفس المخطط، وكل منزل له ألوانه ومحتوياته الخاصة.

### ب. الكلمة المفتاحية `self` 🔑
عندما نكتب دوال داخل الكلاس (نسميها **Methods**)، يجب أن يكون المعامل الأول فيها هو `self`. 
* ما هو `self`؟ هو ببساطة **إشارة إلى الكائن الحالي** الذي يقوم بتنفيذ العملية. يتيح لـ Python معرفة أي كائن بالتحديد نتحدث عنه عندما نعدل خصائصه.

### ج. متغيرات الكلاس (Class Variables) مقابل متغيرات النسخة (Instance Attributes)
* **Instance Attributes:** خصائص خاصة بكل كائن على حدة (مثل: اسم كل طالب، درجته). نعرفها داخل دالة البناء `__init__` باستخدام `self`.
* **Class Variables:** متغيرات مشتركة بين **جميع** الكائنات التي يتم إنشاؤها من نفس الكلاس (مثل: اسم المدرسة، أو نسبة خصم عامة).

---

## 3. أمثلة أكواد برمجية حقيقية 💻

دعنا نبني نظاماً مبسطاً لإدارة طلاب منصة **CodeU** لنرى كيف تعمل الـ Attributes والـ Methods معاً:

```python
class CodeUStudent:
    # Class Variable (متغير مشترك لجميع الطلاب)
    platform_name = "CodeU"
    total_students = 0

    def __init__(self, name, track, points=0):
        # Instance Attributes (خصائص خاصة بكل طالب)
        self.name = name
        self.track = track
        self.points = points
        
        # نزيد عدد الطلاب بواقع 1 كلما تم إنشاء كائن جديد
        CodeUStudent.total_students += 1

    # Instance Method (دالة تخص الكائن)
    def introduce(self):
        return f"مرحباً، أنا {self.name}، أدرس في مسار {self.track} ومنصة {CodeUStudent.platform_name}."

    # Instance Method لتحديث البيانات
    def earn_points(self, new_points):
        self.points += new_points
        return f"رائع! حصل {self.name} على {new_points} نقاط جديدة. المجموع: {self.points}"

# --- تجربة الكود ---
# إنشاء كائنات (Instances) حقيقية
student1 = student2 = None # تعريف مبدئي فقط للتوضيح

student1 = CodeUStudent("أحمد علي", "Python Advanced", 50)
student2 = CodeUStudent("سارة محمد", "AI & Data Science", 80)

# استخدام الـ Methods والـ Attributes
print(student1.introduce()) 
# Output: مرحباً، أنا أحمد علي، أدرس في مسار Python Advanced ومنصة CodeU.

print(student2.earn_points(20))
# Output: رائع! حصل سارة محمد على 20 نقاط جديدة. المجموع: 100

print(f"إجمالي عدد الطلاب المسجلين في {CodeUStudent.platform_name}: {CodeUStudent.total_students}")
# Output: إجمالي عدد الطلاب المسجلين في CodeU: 2
```

---

## 4. تمرين عملي يمهد للخطوة القادمة 🏋️‍♂️

لترسيخ ما تعلمته، أريدك أن تطبق التمرين التالي بنفسك قبل الانتقال للدرس القادم:

**المهمة:**
قم بإنشاء Class باسم `BankAccount` (حساب بنكي):
1. اجعل دالة البناء `__init__` تستقبل: `account_holder` (اسم صاحب الحساب) و `balance` (الرصيد الافتتاحي، واجعله يبدأ بـ `0` افتراضياً).
2. أنشئ Instance Method باسم `deposit(amount)` لتكييف وإضافة مبلغ للرصيد.
3. أنشئ Instance Method باسم `withdraw(amount)` لسحب مبلغ (تأكد أولاً أن الرصيد يكفي، وإلا اطبع رسالة خطأ).
4. أنشئ كائنين لحسابات مختلفة، قم بالإيداع والسحب منهما، واطبع الرصيد النهائي لكليهما.

---
**جاهز؟** اكتب الحل في محرر الكود الخاص بك، واضغط على زر الانتقال للخطوة التالية عندما تتيقن من فهمك التام! بالتوفيق يا مبرمج المستقبل. 💡✨