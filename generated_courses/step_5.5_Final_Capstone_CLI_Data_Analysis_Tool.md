# Advanced Python Concepts
## Final Capstone: CLI Data Analysis Tool

# مرحباً بك في منصة CodeU - الأستاذ الذكي يحييك! 🎓

أهلاً بك أيها المبرمج البارع في الدرس الأخير من قسم مفاهيم بايثون المتقدمة: **[5.5] Final Capstone: CLI Data Analysis Tool**. 
هذه اللحظة هي تتويج لرحلتنا معاً في هذا القسم. لقد تعلمت كيف تستخدم الـ Generators للتعامل مع البيانات الضخمة بذاكرة نظيفة، وكيف تستغل الـ Decorators لإضافة وظائف سحرية لدوالك، وكيف تدير أخطاء النظام باحترافية.

اليوم، سنقوم بدمج **كل** هذه الأدوات لنبني أداة سطر命令 (CLI Tool) حقيقية، جاهزة للإنتاج (Production-ready)، لتحليل البيانات!

---

## 1. ربط ذكي: رحلتنا حتى الآن 🗺️

قبل أن نكتب سطر الكود الأول، دعنا نسترجع ما أحضرناه معنا في حقيبة السفر البرمجية:
1. **المولدات (Generators):** لن نستخدم `read()` لقراءة ملفات ضخمة تحرق الذاكرة، بل سنستخدم `yield` لنقرأ سطراً بسطر.
2. **المزخرفات (Decorators):** سنقوم بقياس أداء أداتنا (كم تستغرق من الوقت؟) ومراقبة الأخطاء عبر Decorator مخصص.
3. **البرمجة الوظيفية ومعالجة الأخطاء:** سنتعامل مع المدخلات غير الصالحة من المستخدم دون أن ينهار التطبيق (Crash).

---

## 2. الشرح العميق: هندسة أداة الـ CLI للبيانات 🛠️

ما هي أداة الـ CLI (Command Line Interface)؟ هي برنامج يعمل من خلال الطرفية (Terminal)، يستقبل مدخلات مثل اسم الملف ونوع التحليل، ويخرج نتائج فورية.

لبناء أداة احترافية، سنتبع معايير هندسية:
* **فصل المسؤوليات (Separation of Concerns):** قراءة البيانات مفصولة عن تحليلها، والتحليل مفصل عن عرض النتائج.
* **المرونة:** استخدام مكتبة بايثون المدمجة `sys` أو `argparse` لاستقبال الوسائط (Arguments).

---

## 3. التطبيق العملي: بناء أداة تحليل البيانات الشاملة 💻

تخيل أن لديك ملف CSV ضخم يحتوي على سجلات مبيعات، وتريد معرفة:
- إجمالي المبيعات.
- متوسط السعر.
- المنتج الأكثر مبيعاً.

كل هذا **دون تحميل الملف بالكامل في الذاكرة**.

### الكود البرمجي الكامل للمشروع (`csv_analyzer.py`):

```python
import csv
import sys
import time
from functools import wraps
from typing import Generator, Dict, Any

# 1. Decorator لحساب وقت التنفيذ وتسجيل الأخطاء
def benchmark_and_log(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[*] Starting execution of: {func.__name__}...")
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            print(f"[+] Successfully executed in {end_time - start_time:.4f} seconds.")
            return result
        except Exception as e:
            print(f"[-] Error in {func.__name__}: {e}", file=sys.stderr)
            sys.exit(1)
    return wrapper

# 2. Generator لقراءة الملف بكفاءة عالية (Memory Efficient)
def stream_csv_data(file_path: str) -> Generator[Dict[str, str], None, None]:
    """يقرأ الملف سطراً بسطر لتوفير الذاكرة."""
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                yield row
    except FileNotFoundError:
        print(f"[-] Error: The file '{file_path}' was not found.", file=sys.stderr)
        sys.exit(1)

# 3. دالة التحليل المتقدمة باستخدام المولدات
@benchmark_and_log
def analyze_sales_data(file_path: str) -> Dict[str, Any]:
    total_sales = 0.0
    total_items = 0
    product_counts: Dict[str, int] = {}

    # استهلاك البيانات عبر الـ Generator
    for row in stream_csv_data(file_path):
        try:
            price = float(row['Price'])
            quantity = int(row['Quantity'])
            product = row['Product']

            total_sales += price * quantity
            total_items += quantity
            
            product_counts[product] = product_counts.get(product, 0) + quantity
        except (ValueError, KeyError) as e:
            # تجاهل السطور التالفة والاستمرار في العمل
            continue

    # إيجاد المنتج الأكثر مبيعاً
    top_product = max(product_counts, key=product_counts.get) if product_counts else "N/A"

    return {
        "Total Revenue": round(total_sales, 2),
        "Total Items Sold": total_items,
        "Best Selling Product": top_product
    }

# 4. نقطة بداية الـ CLI
if __name__ == "__main__":
    # التأكد من تمرير اسم الملف عبر الطرفية
    if len(sys.argv) < 2:
        print("Usage: python csv_analyzer.py <path_to_csv_file>")
        sys.exit(1)

    target_file = sys.argv[1]
    
    print(f"--- Analyzing Data from: {target_file} ---")
    metrics = analyze_sales_data(target_file)

    print("\n=== Analysis Results ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")
```

### كيف تجرب هذا الكود؟
1. أنشئ ملفاً باسم `sales.csv` وضعه في نفس المجلد:
```csv
Product,Price,Quantity
Laptop,1200.50,2
Mouse,25.00,10
Keyboard,75.50,5
Laptop,1200.50,1
```
2. شغل الأداة من الـ Terminal:
```bash
python csv_analyzer.py sales.csv
```

---

## 4. تمرين عملي يمهد للخطوة القادمة 🏋️‍♂️

لقد بنيت للتو نواة أداة تحليل احترافية! لتختبر مهاراتك وتستعد للتحدي القادم في المنصة:
* **المهمة:** قم بتعديل الكود أعلاه ليقبل وسيطاً (Argument) إضافياً عبر `sys.argv` يسمى `--min-price`، بحيث يتجاهل الـ Generator أي منتج سعره أقل من القيمة المحددة من قبل المستخدم.

---
*أتمنى لك التوفيق، وكن جاهزاً للانتقال إلى المستوى التالي في رحلة احتراف بايثون مع CodeU!* 🚀