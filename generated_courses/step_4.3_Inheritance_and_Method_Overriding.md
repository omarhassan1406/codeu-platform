# Object-Oriented Programming (OOP)
## Inheritance and Method Overriding

# منصة CodeU التعليمية 🚀
## الكورس: Programming in Python for Beginners to Advanced
### القسم: Object-Oriented Programming (OOP)
---

# الدرس [4.3]: الوراثة وتجاوز الدوال (Inheritance and Method Overriding)

أهلاً بك يا بطل/بطلة البرمجة في منصة **CodeU**! 🎓
في الدروس السابقة من هذا القسم، تعلمنا كيف نصمم الفئات (Classes) وننشئ الكائنات (Objects)، وكيف نحمي بياناتنا باستخدام مفهوم التغليف (Encapsulation). اليوم، سننتقل إلى المستوى التالي ونفتح الباب أمام أحد أقوى مفاهيم البرمجة الكائنية: **الوراثة (Inheritance)** وكيف نجعل كودنا أكثر ذكاءً وإعادة استخداماً.

---

## 1. ربط سريع بما تم تعلمه سابقاً 🔗

تذكر كيف كنا نصمم فئات لتمثيل أشياء في الواقع؟ مثلاً، إذا طلب منك تصميم نظام لإدارة مدرسة، قد تحتاج إلى إنشاء فئة للمعلم (`Teacher`) وأخرى للطالب (`Student`). 
لو نظرت إلى الفئتين، ستلاحظ أن كليهما يمتلكان نفس الخصائص الأساسية تقريباً: `name` (الاسم)، `age` (العمر)، و `email` (البريد الإلكتروني)، بالإضافة إلى دالة مشتركة مثل `login()`.

بدلًا من كتابة هذه الخصائص والدوال مرتين (تكرار الكود - Don't Repeat Yourself)، تأتي **الوراثة** لتمكننا من تجميع الكود المشترك في فئة واحدة، وجعل الفئات الأخرى ترثه وتضيف عليه ما تحتاجه!

---

## 2. الشرح العميق والمبسط 🧠

### أ. ما هي الوراثة (Inheritance)؟
الوراثة هي مبدأ تبرمجي يسمح لفئة جديدة (تُسمى **Child Class** أو **Subclass**) أن ترث الخصائص (Attributes) والدوال (Methods) من فئة موجودة مسبقاً (تُسمى **Parent Class** أو **Superclass**).

*   **الفئة الأساسية (Parent Class):** الفئة العامة التي تملك الخصائص المشتركة.
*   **الفئة الفرعية (Child Class):** الفئة المتخصصة التي ترث من الأب وتضيف خصائص أو سلوكيات خاصة بها.

### ب. استخدام الدالة `super()`
عندما ترث فئة فرعية من فئة أب، غالباً ما نحتاج إلى استخدام مُنشئ الفئة الأب (`__init__`) لتجنب إعادة كتابة كود تهيئة الخصائص المشتركة. هنا يأتي دور الدالة السحرية `super()`، والتي تعني حرفياً: *"نادِ لي الأب لكي يقوم بعمله الأصلي هنا"*.

### ج. تجاوز الدوال (Method Overriding)
ماذا لو كان الفئة الأب تمتلك دالة معينة، ولكن الفئة الابن تحتاج إلى تنفيذ نفس الدالة بطريقة مختلفة تناسب طبيعتها الخاصة؟
هذا ما يُسمى بـ **Method Overriding** (تجاوز الدوال)؛ حيث تقوم الفئة الابن بإعادة كتابة دالة موجودة في الأب لتمنحها سلوكاً مخصصاً (Specialized Behavior).

---

## 3. أمثلة أكواد برمجية حقيقية 💻

دعنا نطبق هذا بمثال عملي من عالم التجارة الإلكترونية (E-commerce). لنفترض أن لدينا نظام لإدارة المستخدمين في متجر إلكتروني.

```python
# 1. Parent Class (الفئة الأساسية)
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def get_info(self):
        return f"User: {self.name}, Email: {self.email}"

    def dashboard(self):
        return "Loading standard user dashboard..."

# 2. Child Class (الفئة الفرعية التي ترث من User)
class Admin(User):
    def __init__(self, name, email, admin_level):
        # استخدام super() لوراثة خصائص الأب
        super().__init__(name, email)
        self.admin_level = admin_level # خصائص إضافية خاصة بالـ Admin فقط

    # Method Overriding (تجاوز الدالة للحصول على سلوك مخصص)
    def dashboard(self):
        return f"Loading ADMIN dashboard with level {self.admin_level} privileges..."

    def delete_user(self, user_name):
        return f"Admin {self.name} has deleted user: {user_name}"

# --- تجربة الكود ---
# إنشاء كائن من الفئة الأب
standard_user = User("أحمد", "ahmed@codeu.com")
print(standard_user.get_info())
print(standard_user.dashboard())

print("-" * 40)

# إنشاء كائن من الفئة الابن
site_admin = Admin("سارة", "sara@codeu.com", admin_level=5)
print(site_admin.get_info())         # موروثة من User
print(site_admin.dashboard())       # تم تجاوزها (Overridden) لتناسب الـ Admin
print(site_admin.delete_user("خالد")) # دالة خاصة بـ Admin فقط
```

---

## 4. تمرين عملي للتمهيد للخطوة القادمة 🛠️

لكي تثبت المعلومة في ذهنك وتستعد للدرس القادم، قم بحل التحدي التالي:

**اسم التحدي:** نظام إدارة الحيوانات (Animal Kingdom)

1. أنشئ فئة أب اسمها `Animal` تحتوي على:
   - مُنشئ (`__init__`) يأقبل `name` و `sound`.
   - دالة اسمها `make_sound` تطبع صوت الحيوان.
2. أنشئ فئة ابن اسمها `Dog` ترث من `Animal`:
   - تستخدم `super()` لتهيئة الاسم والصوت.
   - تقوم بتجاوز (Override) دالة `make_sound` لتطبع: `f"{self.name} says: Woof! Woof!"`.
   - تضيف دالة جديدة خاصة بالكلاب اسمها `fetch()` تطبع `f"{self.name} is fetching the ball!"`.
3. أنشئ كائناً من `Dog` ونفذ عليه الدوال الثلاث للتأكد من عمل الوراثة و `super()` و Overriding بنجاح.

---
*نراكم في الدرس القادم لنستكشف مفهوماً متقدماً جديداً في الوراثة المتعددة! واصل التميز مع CodeU.* 🌟