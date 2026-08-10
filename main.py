print("🔥 MY SERVER STARTED 🔥")
from fastapi import FastAPI, Form, Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="93a3302f98e8733e4c341443385470cfb8d1844f1f20e6a73337f0feef032760",
    max_age=3600
)
from fastapi.responses import FileResponse, RedirectResponse

@app.get("/")
def home():
    return FileResponse("index.html")
class LoginData(BaseModel):
    username: str
    password: str


@app.get("/admin/login")
def admin_login_page():
    return FileResponse("expert_login.html")


@app.post("/admin/login")
def admin_login(data: LoginData, request: Request):

    # فعلاً برای نسخه آزمایشی
    if data.username == "expert" and data.password == "1234":

        request.session["expert"] = True

        return {
            "status": "ok"
        }

    return {
        "status": "error"
    }
@app.post("/admin/logout-test")
def logout_test():
    print("🔥🔥🔥 LOGOUT TEST HIT 🔥🔥🔥")
    return {"status": "test_ok"}

@app.post("/admin/logout")
def admin_logout(request: Request):
    print("🔥🔥 LOGOUT ROUTE HIT 🔥🔥")

    request.session.clear()

    return {
        "status": "logout_ok"
    }
print("🔥 POST LOGOUT ROUTE LOADED")
@app.get("/admin")
def admin_page(request: Request):

    if not request.session.get("expert"):
        return RedirectResponse(
            "/admin/login",
            status_code=303
        )

    return FileResponse("admin.html")
# مدل ورودی سوال
class Question(BaseModel):
    plotter_type: str
    connection: str
    text: str

# اتصال به دیتابیس
def get_db():
    conn = sqlite3.connect("errors.db")
    conn.row_factory = sqlite3.Row
    return conn
def require_expert(request: Request):

    if not request.session.get("expert"):
        raise HTTPException(
            status_code=401,
            detail="دسترسی فقط برای کارشناس مجاز است"
        )
def normalize(text):
    text = text.lower()

    # یکسان‌سازی حروف عربی و فارسی
    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")

    # حذف نیم‌فاصله
    text = text.replace("‌", "")

    # یکسان‌سازی فاصله‌ها
    text = " ".join(text.split())

    return text.strip()
def normalize_concept(text):
    text = normalize(text)

    word_map = {
        "متوقف شده": "توقف",
        "توقف کرده": "توقف",
        "می لرزد": "لرزیدن",
        "می‌لرزد": "لرزیدن",
        "لرزش": "لرزیدن",
        "کندی": "کند",
        "کند شده": "کند",
        "کند است": "کند",
        "متوقف": "توقف",
    }

    # عبارت‌های چندکلمه‌ای را اول تبدیل می‌کنیم
    for old, new in word_map.items():
        text = text.replace(old, new)

    return text
def concept_match_score(user_text, title, keywords):
    user_text = normalize_concept(user_text)
    title = normalize_concept(title)

    # متن سؤال را به کلمات تبدیل می‌کنیم
    user_words = set(user_text.split())

    score = 0

    # 1. تطبیق عنوان
    title_words = set(title.split())

    for word in title_words:
        if len(word) >= 3 and word in user_words:
            score += 3

    # 2. تطبیق کلمات کلیدی
    keyword_list = [
        normalize_concept(k.strip())
        for k in keywords.replace("،", ",").split(",")
    ]

    for keyword in keyword_list:

        # عبارت چندکلمه‌ای
        if " " in keyword:
            if keyword in user_text:
                score += 5

        # کلمه منفرد
        else:
            if keyword in user_words:
                score += 5

    return score
# جستجو در دیتابیس
from search import search_solution
# ذخیره سوال بدون جواب
def save_unknown(question):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO unknown_questions (question)
        VALUES (?)
    """, (question,))

    conn.commit()
    conn.close()

# API اصلی
@app.post("/ask")
def ask_question(q: Question):
    print("🔥 ASK ENDPOINT CALLED 🔥")

    # جستجو در پایگاه دانش شرکت
    result = search_solution(
        q.text,
        q.plotter_type,
        q.connection
    )

    print("🔥 SEARCH RESULT FROM /ASK:", result)
    print("🔥 QUESTION:", q.text, q.plotter_type, q.connection)

    # -----------------------------
    # پاسخ مستقیم از پایگاه دانش
    # -----------------------------
    if result["type"] == "db":

        return {
            "status": "found",
            "answer": result["data"]["solution"],
            "source": "database"
        }

    # -----------------------------
    # اطمینان متوسط
    # فعلاً پاسخ DB را نشان می‌دهیم
    # و کاربر منتظر کارشناس نمی‌ماند
    # -----------------------------
    elif result["type"] == "hybrid":

        return {
            "status": "found",
            "answer": result["data"]["solution"],
            "source": "database"
        }

    # -----------------------------
    # پاسخ در DB پیدا نشد
    # → AI
    # -----------------------------

    save_unknown(q.text)

    context = get_all_approved()

    ai_answer = ask_ai(q.text, context)

    if ai_answer != "NOT_FOUND":
        save_pending(q.text, ai_answer)

    return {
        "status": "ai_answer",
        "answer": ai_answer,
        "source": "ai"
    }
@app.get("/admin/pending")
def get_pending(request: Request):

    require_expert(request)

    # ادامه کد قبلی بدون تغییر
    import sqlite3, os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "errors.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM pending_answers WHERE status = 0")
    rows = cursor.fetchall()

    conn.close()

    return {"data": rows}


@app.get("/admin/pending/{item_id}")
def get_pending_item(item_id: int, request: Request):

    require_expert(request)

    # ادامه کد قبلی
    import sqlite3, os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "errors.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, question, ai_answer, status
        FROM pending_answers
        WHERE id = ?
    """, (item_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "Not found"}

    return {
        "id": row[0],
        "question": row[1],
        "ai_answer": row[2],
        "status": row[3]
    }
class EditAnswer(BaseModel):
    answer: str


@app.put("/admin/pending/{item_id}")
def edit_pending(
    item_id: int,
    data: EditAnswer,
    request: Request
):

    require_expert(request)

    # ادامه کد قبلی
    import sqlite3, os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "errors.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pending_answers
        SET ai_answer = ?
        WHERE id = ? AND status = 0
    """, (data.answer, item_id))

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Pending item not found"}

    conn.commit()
    conn.close()

    return {
        "status": "updated",
        "id": item_id
    }
@app.post("/admin/approve/{item_id}")
def approve(item_id: int, request: Request):

    require_expert(request)

    # ادامه کد قبلی
    import sqlite3, os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "errors.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # گرفتن آخرین نسخه پاسخ کارشناس
    cursor.execute("""
        SELECT question, ai_answer
        FROM pending_answers
        WHERE id = ? AND status = 0
    """, (item_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": "Pending item not found or already approved"}

    question, answer = row

    # انتقال پاسخ نهایی به جدول errors
    cursor.execute("""
        INSERT INTO errors
        (plotter_type, connection, title, keywords, solution, approved)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "نامشخص",
        "نامشخص",
        question,
        question,
        answer,
        1
    ))

    # علامت‌گذاری Pending به عنوان تاییدشده
    cursor.execute("""
        UPDATE pending_answers
        SET status = 1
        WHERE id = ?
    """, (item_id,))

    conn.commit()
    conn.close()

    return {
        "status": "approved",
        "id": item_id
    }
@app.post("/admin/reject/{item_id}")
def reject_pending(item_id: int, request: Request):

    require_expert(request)

    # ادامه کد قبلی
    import sqlite3

    conn = sqlite3.connect("errors.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM pending_answers WHERE id = ? AND status = 0",
        (item_id,)
    )

    conn.commit()
    conn.close()

    return {
        "status": "rejected",
        "id": item_id
    }
@app.post("/admin/knowledge")
def add_knowledge(
    request: Request,
    plotter_type: str = Form(...),
    connection: str = Form(...),
    title: str = Form(...),
    keywords: str = Form(...),
    solution: str = Form(...)
):

    require_expert(request)

    # ادامه کد قبلی
    plotter_type: str = Form(...),
    connection: str = Form(...),
    title: str = Form(...),
    keywords: str = Form(...),
    solution: str = Form(...)
    import sqlite3

    conn = sqlite3.connect("errors.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO errors
        (plotter_type, connection, title, keywords, solution, approved)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (
        plotter_type,
        connection,
        title,
        keywords,
        solution
    ))

    new_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "status": "added",
        "id": new_id
    }
print("🔥 FINAL REGISTERED ROUTES:")

for route in app.routes:
    print("➡️", route.path, route.methods)
def extract_avalai_answer(result):
    try:
        # حالت 1: output_text مستقیم
        if "output_text" in result and result["output_text"]:
            return result["output_text"]

        # حالت 2: ساختار output
        if "output" in result and len(result["output"]) > 0:
            contents = result["output"][0].get("content", [])

            for item in contents:
                if item.get("type") == "output_text":
                    return item.get("text")

        return None

    except Exception:
        return None
def ask_ai(question, context):
    import requests
    print("ASK_AI CALLED")
    url = "https://api.avalai.ir/v1/responses"

    headers = {
        "Authorization": "Bearer aa-wt4O4OOlzOLG5OYhP7xiMpuVpsmTkqXsWYwDCx9OiXytrW2J",
        "Content-Type": "application/json"
    }

    prompt = f"""
    اگر پاسخ در اطلاعات زیر وجود دارد، از همان استفاده کن.

    اگر وجود ندارد:
    ابتدا راه‌حل‌های ساده و رایج را پیشنهاد بده (مثل برق، کابل، تنظیمات).
    اگر واقعاً هیچ راه‌حلی نمی‌دانی، بگو: نیاز به بررسی بیشتر دارد.

    پاسخ کوتاه و کاربردی باشد.

    اطلاعات:
    {context}

    سوال:
    {question}
    """

    data = {
        "model": "gpt-4.1-mini",
        "input": prompt
    }

    try:
        print("CONTEXT:", context)
        response = requests.post(url, headers=headers, json=data)

        print("========== DEBUG ==========")
        print("STATUS:", response.status_code)
        print("RAW:", response.text)
        print("===========================")

        result = response.json()

        answer = extract_avalai_answer(result)

        if not answer:
            return "NOT_FOUND"

        return answer.strip()

    except Exception as e:
        return f"خطا در ارتباط با AI: {str(e)}"
def save_pending(question, answer):
    import sqlite3
    import os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "errors.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pending_answers (question, ai_answer)
        VALUES (?, ?)
    """, (question, answer))

    conn.commit()
    conn.close()
def get_all_approved():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT title, solution FROM errors WHERE approved = 1")
    rows = cursor.fetchall()
    conn.close()

    context = ""
    for row in rows:
        context += f"خطا: {row['title']}\nراه حل: {row['solution']}\n\n"

    return context
@app.get("/test")
def test():
    print("TEST ENDPOINT HIT")
    return {"msg": "ok"}
@app.get("/debug")

def debug():
    print("🔥 DEBUG ENDPOINT HIT 🔥")
    return {"msg": "debug ok"}