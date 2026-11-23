# Object-Oriented Programming (OOP)
## Encapsulation and Polymorphism

أهلاً بك يا بطل/ة في منصة **CodeU**! 🚀 

أنا أستاذك الذكي، ومرافقك في هذه الرحلة الممتعة لاحتراف البرمجة. لقد قطعت شوطاً رائعاً حتى الآن في رحلة تعلم بايثون، ووصلنا اليوم إلى محطة بالغة الأهمية وعميقة التأثير: **البرمجة الكائنية (OOP)**، وتحديداً مفهوما: **التغليف (Encapsulation)** و**تعدد الأشكال (Polymorphism)**.

---

# الدرس [4.4]: Encapsulation and Polymorphism

## 1. ربط سريع بما تم تعلمه سابقاً 🔗
في الدروس السابقة من قسم الـ OOP، تعلمنا كيف نصمم "القوالب" (Classes) وننشئ منها "الكائنات" (Objects)، وتعرفنا على مفهوم **الميراث (Inheritance)** الذي يتيح لنا توريث الخصائص والدوال من كلاس أساسي إلى كلاس فرعي، مما يوفر علينا كتابة كود مكرر. 

لكن، ماذا لو أردنا حماية بعض بيانات الكلاس من العبث الخارجي؟ وماذا لو أردنا لنفس الدالة أن تتصرف بشكل مختلف بناءً على الكائن الذي يستدعيها؟ هذا تماماً ما سنتعلمه اليوم عبر **Encapsulation** و **Polymorphism**.

---

## 2. الشرح العميق والمبسط 🧠

### أولاً: التغليف (Encapsulation)
التغليف هو مبدأ إخفاء بيانات الكائن الحساسة عن العالم الخارجي، والسماح بالوصول إليها أو تعديلها بطرق آمنة ومراقبة. في بايثون، نميز بين ثلاثة أنواع من الأعضاء (Members):
1. **Public (عام):** يمكن الوصول إليه من أي مكان (داخل الكلاس أو خارجه).
2. **Protected (محمي):** يُرمز له بشرطة سفلى واحدة `_`، ويُشير إلى أن هذا المتغير مخصص للاستخدام داخل الكلاس والكلاسات الوارثة منه فقط (conventionally).
3. **Private (خاص):** يُرمز له بشرطة سفلى مزدوجة `__`، ويقوم المترجم بـ "Name Mangling" لحمايته ومنع الوصول المباشر إليه من خارج الكلاس.

وللتعامل مع البيانات الخاصة بأمان، نستخدم:
* **Getters:** دوال لجلب قيم المتغيرات الخاصة.
* **Setters:** دوال لتعديل قيم المتغيرات الخاصة مع إضافة شروط تحقق (Validation).
* **Property Decorators (`@property`):** طريقة بايثون الأنيقة للتعامل مع الـ Getters والـ Setters كأنها متغيرات عادية.

### ثانياً: تعدد الأشكال (Polymorphism)
 وتعني حرفياً "أشكال متعددة". في البرمجة، تعني إمكانية استخدام نفس اسم الدالة أو الواجهة (Interface) مع أنواع مختلفة من البيانات أو الكائنات، وكل كائن سيقوم بالتنفيذ بالطريقة التي تناسبه.

---

## 3. أمثلة أكواد برمجية (تطبيقات حقيقية) 💻

لنفترض أننا نبني نظام إدارة بنكي (Banking System) يطبق مبادئ الـ OOP باحترافية:

```python
class BankAccount:
    def __init__(self, owner: str, balance: float):
        self.owner = owner                 # Public attribute
        self._account_type = "Savings"     # Protected attribute
        self.__balance = balance           # Private attribute (محمي تماماً)

    # Getter باستخدام الـ Property Decorator
    @property
    def balance(self):
        return self.__balance

    # Setter للتحقق من صحة المبلغ قبل إضافته
    @balance.setter
    def balance(self, amount):
        if amount >= 0:
            self.__balance = amount
        else:
            print("❌ خطأ: لا يمكن أن يكون الرصيد سالباً!")

    def deposit(self, amount):
        if amount > 0:
            self.__balance += amount
            print(تم إيداع {amount}. الرصيد الحالي: {self.__balance})
        else:
            print("مبلغ الإيداع غير صالح.")

# تطبيق الـ Polymorphism (تعدد الأشكال)
class NotificationSystem:
    def send_alert(self, message):
        pass  # واجهة عامة

class EmailNotification(NotificationSystem):
    def send_alert(self, message):
        print(f"📧 إرسال بريد إلكتروني: {message}")

class SMSNotification(NotificationSystem):
    def send_alert(self, message):
        print(f"📱 إرسال رسالة نصية SMS: {message}")

# --- اختبار الكود ---
# 1. تجربة التغليف Encapsulation
my_account = "أحمد", 1000)
my_account.deposit(500)

# محاولة الوصول للرصيد بالطريقة الآمنة (Getter)
print(f"الرصيد النهائي: {my_account.balance}")

# محاولة تعديل الرصيد بقيمة سالبة عبر الـ Setter
my_account.balance = -200  # سيعطي خطأ ولا يتم التعديل

# 2. تجربة تعدد الأشكال Polymorphism
notifications = [EmailNotification(), SMSNotification()]

for notif in notifications:
    notif.send_alert("تنبيه أمني: تم تسجيل الدخول لحسابك.")
```

---

## 4. تمرين عملي (مهد للخطوة القادمة) 🏋️‍♂️

لترسخ هذه المفاهيم في ذهنك، أطلب منك كتابة كود صغير بالتنسيق التالي:
1. أنشئ كلاس اسمه `Employee` (موظف).
2. اجعل اسم الموظف `name` (عام)، وراتبه `__salary` (خاص).
3. استخدم `@property` و الـ setter للتحقق من أن الراتب المدخل لا يقل عن الحد الأدنى للأجور (مثلاً 3000)، وإذا كان أقل، اطبع رسالة خطأ.
4. أنشئ كلاسين فرعيين `Manager` و `Developer` يرثان من `Employee` ويطبقان دالة `calculate_bonus()` بشكل مختلف (تطبيق Polymorphism).

شاركني حلك في محرر الكود الخاص بك، واستعد للخطوة القادمة في رحلتنا مع CodeU! بالتوفيق يا بطل! 🌟