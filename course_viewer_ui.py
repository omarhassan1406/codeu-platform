import streamlit as st
import json
import os

from app.core.course_paths import MANIFEST_FILENAME, ROADMAP_FILENAME, lesson_filename

# تحديد مسار مجلد الكورسات بناءً على مكان وجود ملف الـ UI
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "generated_courses")

# إعداد صفحة الـ UI
st.set_page_config(
    page_title="CodeU Course Reviewer", 
    page_icon="🎓", 
    layout="wide"
)

st.title("🎓 CodeU - لوحة مراجعة محتوى الكورسات")
st.markdown("استعرض هيكل الكورس، الأقسام، الخطوات، والسكريبتات التعليمية بدقة لمراجعتها واكتشاف أي ملاحظات.")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

# كل كورس في مجلد خاص به يحتوي على roadmap.json
course_dirs = sorted(
    d for d in os.listdir(OUTPUT_DIR)
    if os.path.isfile(os.path.join(OUTPUT_DIR, d, ROADMAP_FILENAME))
)

if not course_dirs:
    st.warning("⚠️ لا توجد كورسات مسجلة حتى الآن في المجلد. قم بتشغيل سكريبت توليد الكورس أولاً.")
else:
    # قائمة منسدلة لاختيار الكورس في الشريط الجانبي
    st.sidebar.header("📁 إدارة الكورسات")
    selected_course = st.sidebar.selectbox("اختر الكورس للاستعراض:", course_dirs)
    selected_dir = os.path.join(OUTPUT_DIR, selected_course)
    file_path = os.path.join(selected_dir, ROADMAP_FILENAME)
    
    with open(file_path, "r", encoding="utf-8") as f:
        roadmap_data = json.load(f)
        
    st.sidebar.markdown(f"**📌 عنوان الكورس:** {roadmap_data.get('course_title')}")
    st.sidebar.markdown(f"**🎯 المستوى:** {roadmap_data.get('target_audience')}")
    manifest_path = os.path.join(selected_dir, MANIFEST_FILENAME)
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        st.sidebar.markdown(
            f"**🧾 حالة التوليد:** {manifest.get('status')} "
            f"({len(manifest.get('completed_steps', []))}/{manifest.get('total_steps')})"
        )
    st.sidebar.markdown("---")
    
    # عرض محتوى الكورس في الشريط الجانبي على شكل أقسام وخطوات (شبيه بـ Udemy)
    st.sidebar.header("📚 محتوى الكورس (Sections)")
    
    # تهيئة الـ Session State لحفظ الدرس المختار
    if 'current_section' not in st.session_state:
        st.session_state['current_section'] = None
    if 'current_step' not in st.session_state:
        st.session_state['current_step'] = None

    for section in roadmap_data.get("sections", []):
        with st.sidebar.expander(f"📌 {section['section_id']}: {section['section_title']}"):
            st.caption(section['description'])
            for step in section['steps']:
                button_label = f"{step['step_id']} - {step['step_title']}"
                if st.button(button_label, key=f"btn_{selected_course}_{step['step_id']}"):
                    st.session_state['current_section'] = section['section_title']
                    st.session_state['current_step'] = step

    # ==========================================
    # منطقة عرض وتدقيق المحتوى في الواجهة الرئيسية
    # ==========================================
    st.header("📖 معاينة السكريبت ومحتوى الدرس")
    
    if st.session_state['current_step'] is not None:
        curr_sec = st.session_state['current_section']
        curr_st = st.session_state['current_step']
        
        # عرض تفاصيل الدرس
        st.subheader(f"📂 القسم: {curr_sec}")
        st.markdown(f"### 📝 الدرس: [{curr_st['step_id']}] {curr_st['step_title']}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="⏱️ الوقت المتوقع", value=f"{curr_st['duration_mins']} دقيقة")
        with col2:
            st.markdown(f"**🎯 الأهداف التعليمية:**")
            for obj in curr_st['learning_objectives']:
                st.markdown(f"- {obj}")
                
        st.markdown("---")
        
        # البحث عن ملف الـ Markdown الخاص بالدرس لعرضه
        md_filename = lesson_filename(curr_st['step_id'], curr_st['step_title'])
        md_path = os.path.join(selected_dir, md_filename)
        
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as md_file:
                markdown_content = md_file.read()
            
            # عرض المحتوى بتنسيق Markdown احترافي مع إمكانية التعديل للمراجعة إن أردت
            st.markdown("#### 📄 سكريبت الشرح والأكواد:")
            st.markdown(markdown_content)
            
        else:
            st.warning(f"⚠️ لم يتم العثور على ملف السكريبت لهذا الدرس ({md_filename}). تأكد من اكتمال توليد الكورس.")
            
    else:
        st.info("👈 قم باختيار أي درس من القائمة الجانبية (Sidebar) لعرض السكريبت الخاص به ومراجعته.")