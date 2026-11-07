# Object-Oriented Programming (OOP)
## Section 4 Capstone: Bank Account System

أهلاً بك يا بطل/ة في منصة **CodeU** البرمجية! 🚀
أنا أستاذك الذكي، ومرافقك في رحلة احتراف البرمجة. لقد قطعنا شوطاً متميزاً في دورة **"Programming in Python for Beginners to Advanced"**.

نصل اليوم إلى المحطة الأهم في قسم البرمجة الكائنية الصنع: **مشروع التخرج للقسم (Section 4 Capstone)**، حيث سنقوم ببناء نظام مصرفي متكامل (Bank Account System).

---

# [4.5] Section 4 Capstone: Bank Account System

## 1. ربط سريع بما تم تعلمه سابقاً 🔗
في الدروس السابقة من هذا القسم (OOP)، غطمنا مفاهيم قوية جداً:
* **Classes & Objects:** كيف ننشئ قوالب ونأخذ منها كائنات حية في الذاكرة.
* **Encapsulation (التغليف):** كيف نحمي بياناتنا الحساسة باستخدام `private variables` (`__`) والـ `Getters & Setters`.
* **Inheritance (الوراثة):** كيف نورث الخصائص والمطرق من الكلاس الأساسي (`Parent`) إلى الكلاسات الفرعية (`Child`).
* **Polymorphism (تعدد الأشكال):** كيف نستخدم نفس الدالة بسلوك مختلف باختلاف الكائن.

اليوم، سنقوم **بدمج كل هذه المفاهيم معاً** في مشروع عملي واقعي يحاكي النظام الحقيقي للبنوك!

---

## 2. الشرح العميق والمبسط للمشروع 💡

تخيل أننا نبغي تطوير نظام لـ "بنك CodeU". البنك لا يحتوي على نوع واحد من الحسابات، بل أنواع متعددة:
1. **حساب جاري (Savings Account):** يسمح بالإيداع والسحب، ولكنه يفرض رسوماً على السحب أو يتطلب حداً أدنى للرصيد.
2. **حساب أعمال (Business Account):** يسمح بعمليات سحب أكبر، وربما يحصل على فوائد أو يعتمد على شروط خاصة.

لذلك، سيكون لدينا **تصميم متعدد الكلاسات (Multi-class System)** يعتمد بشكل أساسي على **الوراثة (Inheritance)** و **التغليف (Encapsulation)** لضمان أمان أموال العملاء (لا يمكن لأحد تعديل الرصيد مباشرة عبر `account.__balance = 1000000`!).

### هيكل المشروع (Class Diagram Design):
* **`Account` (Base Class):** الكلاس الأب، يحوي الخصائص المشتركة (`account_number`, `owner`, `__balance`) والدوال الأساسية (`deposit`, `get_balance`).
* **`SavingsAccount` (Derived Class):** يورث من `Account` ويضيف ميزة نسبة الفائدة (`interest_rate`).
* **`Bank` (Management Class):** كلاس لإدارة جميع الحسابات في البنك (إضافة حساب، البحث عن حساب، عرض كل الحسابات).

---

## 3. أمثلة أكواد برمجية نظيفة وتطبيقية 💻

دعنا نبني هذا النظام خطوة بخطوة بلغة بايثون نظيفة وقابلة للتوسع:

```python
# --- الخطوة 1: الكلاس الأساسي (Account) مع تطبيق Encapsulation ---
class Account:
    def __init__(self, account_number: str, owner: str, initial_balance: float = 0.0):
                self.account_number = account_number
        self.owner = owner
        self.__balance = initial_balance  # خاصية محمية (Private)

    def deposit(self, amount: float):
        """إيداع مبلغ في الحساب"""
        if amount > 0:
            self.__balance += amount
            print(f"✅ تمت عملية الإيداع بنجاح. الرصيد الحالي: ${self.__balance:.2f}")
        else:
            print("❌ مبلغ الإيداع يجب أن يكون أكبر من الصفر.")

    def withdraw(self, amount: float):
        """سحب مبلغ من الحساب مع التحقق من الرصيد"""
        if 0 < amount <= self.__balance:
            self.__balance -= amount
            print(f"✅ تم سحب ${amount:.2f} بنجاح. الرصيد المتبقي: ${self.__balance:.2f}")
        else:
            print("❌ عملية مرفوضة: رصيد غير كافٍ أو مبلغ غير صالح.")

    def get_balance(self) -> float:
        """Getter آمن للرصيد"""
        return self.__balance

    def account_info(self):
        print(f"🏦 رقم الحساب: {self.account_number} | المالك: {self.owner} | الرصيد: ${self.__balance:.2f}")


# --- الخطوة 2: الكلاس الفرعي (SavingsAccount) باستخدام Inheritance ---
class SavingsAccount(Account):
    def __init__(self, account_number: str, owner: str, initial_balance: float = 0.0, interest_rate: float = 0.02):
        super().__init__(account_number, owner, initial_balance)
        self.interest_rate = interest_rate  # نسبة الفائدة

    def apply_interest(self):
        """إضافة الفائدة السنوية إلى الرصيد"""
        interest = self.get_balance() * self.interest_rate
        self.deposit(interest)
        print(f"📈 تم تطبيق نسبة فائدة قدرها {self.interest_rate * 100}%. تمت إضافة ${interest:.2f}")


# --- الخطوة 3: كلاس إدارة البنك (Bank Management) ---
class Bank:
    def __init__(self, name: str):
        self.name = name
        self.accounts = {}  # لتخزين الحسابات باستخدام رقم الحساب كـ Key

    def add_account(self, account: Account):
        if account.account_number not in self.accounts:
            self.accounts[account.account_number] = account
            print(f"🎉 تم فتح الحساب رقم {account.account_number} في بنك {self.name}.")
        else:
            print("⚠️ رقم الحساب موجود مسبقاً!")

    def get_account(self, account_number: str) -> Account:
        return self.accounts.get(account_number, None)


# ==========================================
# تجربة النظام (Testing our Bank System)
# ==========================================
if __name__ == "__main__":
    # 1. إنشاء البنك
    my_bank = Bank("CodeU National Bank")

    # 2. إنشاء حساب توفير
    acc1 = SavingsAccount("ACC-101", "أحمد علي", 1000.0, 0.05)
    
    # 3. إضافة الحساب للبنك
    my_bank.add_account(acc1)

    # 4. تجربة العمليات
    print("\n--- بدء العمليات المصرفية ---")
    acc1.account_info()
    
    acc1.deposit(500)      # إيداع
    acc1.withdraw(200)     # سحب
    acc1.apply_interest()  # تطبيق الفائدة
    
    # محاولة الوصول غير الآمن للرصيد (ستفشل أو تعطي خطأ)
    try:
        print(acc1.__balance)
    except AttributeError:
        print("🛡️ الحماية تعمل بكفاءة! لا يمكن الوصول للرصيد مباشرة (`__balance`).")
```

---

## 4. التمرين العملي يمهد للخطوة القادمة 🏋️‍♂️

لكي تضمن استيعابك الكامل وتستعد للتحدي القادم، المطلوب منك الآن:

1. **إضافة كلاس جديد:** قم بإنشاء كلاس فرعي جديد باسم `BusinessAccount` يرث من `Account`.
2. **الميزات المطلوبة:** 
   * اجعل `BusinessAccount` يفرض رسوماً ثابتة قدرها `$5` مع كل عملية سحب (Transaction Fee).
   * تجاوز (Override) دالة `withdraw` لتطبيق هذه الرسوم.
3. **التحدي:** اختبر الكلاس الجديد وأضفه إلى نظام `Bank` الذي أنشأناه.

---
شارك كود الحل الخاص بك في منصة **CodeU**، ودعنا نناقش النتائج معاً لكي تنتقل بثقة إلى القسم التالي! بالتوفيق يا بطل! 🌟