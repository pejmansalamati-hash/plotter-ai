print("🔥 MY SERVER STARTED 🔥")
from fastapi import FastAPI, Form, Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from search import detect_concepts
import sqlite3
DB_NAME = "errors.db"
app = FastAPI()
from fastapi.responses import FileResponse, RedirectResponse
@app.post("/search")
async def search(q: str = Form(...)):
    try:
        result = search_solution(q)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}
app.add_middleware(
    SessionMiddleware,
    secret_key="93a3302f98e8733e4c341443385470cfb8d1844f1f20e6a73337f0feef032760",
    max_age=3600
)


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

@app.get("/admin/concepts")
def get_concepts(request: Request):

    require_expert(request)

    conn = get_db()

    rows = conn.execute("""
        SELECT DISTINCT concept
        FROM concepts
        WHERE active=1
        ORDER BY concept
    """).fetchall()

    conn.close()

    return {
        "data": [r["concept"] for r in rows]
    }
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
    import os
    import shutil

    base_dir = os.path.dirname(os.path.abspath(__file__))
    source_db = os.path.join(base_dir, "errors.db")
    persistent_db = "/data/errors.db"

    # اگر دیتابیس روی دیسک پایدار وجود ندارد،
    # نسخه فعلی را فقط یک بار به آنجا منتقل می‌کنیم.
    if not os.path.exists(persistent_db):
        if not os.path.exists(source_db):
            raise FileNotFoundError(
                f"فایل دیتابیس اولیه پیدا نشد: {source_db}"
            )

        shutil.copy2(source_db, persistent_db)
        print("DATABASE COPIED TO PERSISTENT DISK")

    conn = sqlite3.connect(persistent_db, timeout=30)
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
    import traceback

    conn = None

    try:
        print("DEBUG SAVE_UNKNOWN: opening database")
        conn = get_db()
        cursor = conn.cursor()

        print("DEBUG SAVE_UNKNOWN: checking table")

        cursor.execute("""
            INSERT INTO unknown_questions (question)
            VALUES (?)
        """, (question,))

        conn.commit()
        print("DEBUG SAVE_UNKNOWN: saved successfully")

    except Exception as e:
        print("SAVE_UNKNOWN ERROR TYPE:", type(e).__name__)
        print("SAVE_UNKNOWN ERROR:", repr(e))
        traceback.print_exc()
        raise

    finally:
        if conn is not None:
            conn.close()
    
# "/test-avalai"
@app.get("/test-avalai")
def test_avalai():
    import requests
    import os

    url = "https://api.avalai.ir/v1/responses"

    api_key = os.getenv("AVALAI_API_KEY")

    if not api_key:
        return {
            "status": "failed",
            "error": "AVALAI_API_KEY پیدا نشد"
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4.1-mini",
        "input": "سلام. فقط پاسخ بده: تست موفق است."
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        return {
            "status": "response_received",
            "http_status": response.status_code,
            "response": response.text
        }

    except Exception as e:
        return {
            "status": "failed",
            "error_type": type(e).__name__,
            "error": str(e)
        }
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

    print("DEBUG 1: BEFORE save_unknown")

    save_unknown(q.text)

    print("DEBUG 2: AFTER save_unknown")

    # چون پاسخ مرتبطی در DB پیدا نشده،
    # زمینه نامرتبط به AI ارسال نمی‌کنیم.
    context = ""

    print("DEBUG 3: EMPTY CONTEXT - ROUTING TO AI")

    ai_answer = ask_ai(
    q.text,
    context,
    q.plotter_type,
    q.connection
)

    print("DEBUG 4: AFTER ask_ai")

    if ai_answer != "NOT_FOUND":
        save_pending(
            q.text,
            ai_answer,
            q.plotter_type,
            q.connection
        )

    return {
        "status": "ai_answer",
        "answer": ai_answer,
        "source": "ai"
    }

@app.get("/admin/pending")
def get_pending(request: Request):

    require_expert(request)

    # ادامه کد قبلی بدون تغییر
    conn = get_db()
    cursor = conn.cursor()

    
    cursor.execute("""
        SELECT id, question, ai_answer, status
        FROM pending_answers
        WHERE status = 0
    """)
    rows = cursor.fetchall()

    data = [
        {
        "id": row["id"],
        "question": row["question"],
        "ai_answer": row["ai_answer"],
        "status": row["status"]
        }
        for row in rows
    ]

    conn.close()

    return {"data": data}


@app.get("/admin/pending/{item_id}")
def get_pending_item(item_id: int, request: Request):

    require_expert(request)

    # ادامه کد قبلی
    conn = get_db()
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
    conn = get_db()
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

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. دریافت سؤال، پاسخ و مشخصات دستگاه
        cursor.execute("""
            SELECT question, ai_answer, plotter_type, connection
            FROM pending_answers
            WHERE id = ? AND status = 0
        """, (item_id,))

        row = cursor.fetchone()

        if not row:
            return {
                "error": "Pending item not found or already approved"
            }

        question = row["question"]
        answer = row["ai_answer"]
        plotter_type = row["plotter_type"] or "نامشخص"
        connection = row["connection"] or "نامشخص"

        # 2. ذخیره پاسخ تأییدشده در پایگاه دانش
        cursor.execute("""
            INSERT INTO errors
                (plotter_type, connection, title, keywords, solution, approved)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            plotter_type,
            connection,
            question,
            question,
            answer,
            1
        ))

        error_id = cursor.lastrowid

        # 3. شناسایی مفهوم با الگوریتم فعلی
        detected_concepts = detect_concepts(question)
        detected_codes = [
            item["concept"] for item in detected_concepts
        ]

        print("APPROVE QUESTION:", repr(question))
        print("APPROVE DETECTED CONCEPTS:", detected_codes)

        # 4. اتصال رکورد به مفهوم‌های موجود
        concept_ids = []

        for concept_code in detected_codes:
            cursor.execute("""
                SELECT id
                FROM concepts
                WHERE concept = ?
                  AND active = 1
                LIMIT 1
            """, (concept_code,))

            concept_row = cursor.fetchone()

            if concept_row:
                concept_ids.append(concept_row["id"])

        for concept_id in concept_ids:
            cursor.execute("""
                INSERT INTO error_concepts
                    (error_id, concept_id, weight)
                VALUES (?, ?, ?)
            """, (error_id, concept_id, 10))

        # 5. علامت‌گذاری سؤال به‌عنوان تأییدشده
        cursor.execute("""
            UPDATE pending_answers
            SET status = 1
            WHERE id = ? AND status = 0
        """, (item_id,))

        if cursor.rowcount != 1:
            raise Exception("Pending item status could not be updated")

        # 6. ثبت همه تغییرات
        conn.commit()

        print("APPROVED ERROR ID:", error_id)
        print("APPROVED PLOTTER TYPE:", plotter_type)
        print("APPROVED CONNECTION:", connection)
        print("LINKED CONCEPT IDS:", concept_ids)

        return {
            "status": "approved",
            "id": item_id,
            "error_id": error_id,
            "plotter_type": plotter_type,
            "connection": connection,
            "linked_concepts": len(concept_ids)
        }

    except Exception as e:
        conn.rollback()
        print("APPROVE ERROR:", repr(e))
        return {"error": str(e)}

    finally:
        conn.close()


@app.post("/admin/reject/{item_id}")
def reject_pending(item_id: int, request: Request):

    require_expert(request)

    # ادامه کد قبلی
    conn = get_db()
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
 # ============================================================
# مدیریت پایگاه دانش شرکت
# ============================================================

@app.get("/admin/errors")
def get_errors(request: Request):

    require_expert(request)

    conn = get_db()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                plotter_type,
                connection,
                title,
                keywords,
                solution,
                approved
            FROM errors
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        data = []

        for row in rows:

            data.append({
                "id": row["id"],
                "plotter_type": row["plotter_type"],
                "connection": row["connection"],
                "title": row["title"],
                "keywords": row["keywords"],
                "solution": row["solution"],
                "approved": row["approved"]
            })

        return {
            "status": "ok",
            "data": data
        }

    except Exception as e:

        print("❌ GET ERRORS ERROR:", repr(e))

        return {
            "status": "error",
            "message": str(e)
        }

    finally:

        conn.close()


class EditKnowledge(BaseModel):

    plotter_type: str
    connection: str
    title: str
    keywords: str
    solution: str


@app.put("/admin/errors/{error_id}")
def edit_error(
    error_id: int,
    data: EditKnowledge,
    request: Request
):

    require_expert(request)

    conn = get_db()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            UPDATE errors
            SET
                plotter_type = ?,
                connection = ?,
                title = ?,
                keywords = ?,
                solution = ?
            WHERE id = ?
        """, (
            data.plotter_type,
            data.connection,
            data.title,
            data.keywords,
            data.solution,
            error_id
        ))

        if cursor.rowcount == 0:

            return {
                "status": "error",
                "message": "رکورد موردنظر پیدا نشد."
            }

        conn.commit()

        print("🔥 KNOWLEDGE UPDATED:", error_id)

        return {
            "status": "updated",
            "id": error_id
        }

    except Exception as e:

        conn.rollback()

        print("❌ EDIT ERROR:", repr(e))

        return {
            "status": "error",
            "message": str(e)
        }

    finally:

        conn.close()


@app.delete("/admin/errors/{error_id}")
def delete_error(
    error_id: int,
    request: Request
):

    require_expert(request)

    conn = get_db()
    cursor = conn.cursor()

    try:

        # ابتدا Relationهای مربوط به این Error را حذف می‌کنیم
        cursor.execute("""
            DELETE FROM error_concepts
            WHERE error_id = ?
        """, (error_id,))

        deleted_relations = cursor.rowcount

        # سپس خود Error را حذف می‌کنیم
        cursor.execute("""
            DELETE FROM errors
            WHERE id = ?
        """, (error_id,))

        if cursor.rowcount == 0:

            conn.rollback()

            return {
                "status": "error",
                "message": "رکورد موردنظر پیدا نشد."
            }

        conn.commit()

        print("🔥 KNOWLEDGE DELETED:", error_id)
        print("DELETED RELATIONS:", deleted_relations)

        return {
            "status": "deleted",
            "id": error_id
        }

    except Exception as e:

        conn.rollback()

        print("❌ DELETE ERROR:", repr(e))

        return {
            "status": "error",
            "message": str(e)
        }

    finally:

        conn.close()   
@app.put("/admin/errors/{error_id}")
def edit_error(
    error_id: int,
    request: Request,
    data: dict
):

    require_expert(request)

    conn = get_db()
    cursor = conn.cursor()

    try:

        # بررسی وجود رکورد
        cursor.execute("""
            SELECT id
            FROM errors
            WHERE id = ?
        """, (error_id,))

        row = cursor.fetchone()

        if not row:
            return {
                "status": "error",
                "message": "رکورد پیدا نشد"
            }

        # ویرایش اطلاعات
        cursor.execute("""
            UPDATE errors
            SET
                plotter_type = ?,
                connection = ?,
                title = ?,
                keywords = ?,
                solution = ?
            WHERE id = ?
        """, (
            data.get("plotter_type"),
            data.get("connection"),
            data.get("title"),
            data.get("keywords"),
            data.get("solution"),
            error_id
        ))

        conn.commit()

        print("🔥 ERROR UPDATED:", error_id)

        return {
            "status": "updated",
            "id": error_id
        }

    except Exception as e:

        conn.rollback()

        print("❌ ERROR UPDATE:", repr(e))

        return {
            "status": "error",
            "message": str(e)
        }

    finally:

        conn.close()


@app.delete("/admin/errors/{error_id}")
def delete_error(
    error_id: int,
    request: Request
):

    require_expert(request)

    conn = get_db()
    cursor = conn.cursor()

    try:

        # ابتدا Relationهای مربوط به رکورد را حذف می‌کنیم
        cursor.execute("""
            DELETE FROM error_concepts
            WHERE error_id = ?
        """, (error_id,))

        # سپس خود رکورد را حذف می‌کنیم
        cursor.execute("""
            DELETE FROM errors
            WHERE id = ?
        """, (error_id,))

        if cursor.rowcount == 0:

            conn.rollback()

            return {
                "status": "error",
                "message": "رکورد پیدا نشد"
            }

        conn.commit()

        print("🗑️ ERROR DELETED:", error_id)

        return {
            "status": "deleted",
            "id": error_id
        }

    except Exception as e:

        conn.rollback()

        print("❌ ERROR DELETE:", repr(e))

        return {
            "status": "error",
            "message": str(e)
        }

    finally:

        conn.close()
@app.post("/admin/knowledge")

def add_knowledge(
    request: Request,
    plotter_type: str = Form(...),
    connection: str = Form(...),
    title: str = Form(...),
    concepts: str = Form(...),
    solution: str = Form(...)
):

    require_expert(request)

    import json
    import sqlite3

    conn = get_db()
    cursor = conn.cursor()

    try:

        # =====================================================
        # 1. تبدیل Concepts دریافتی از HTML
        # =====================================================

        try:
            concept_names = json.loads(concepts)
        except json.JSONDecodeError:
            return {
                "status": "error",
                "message": "فرمت Concepts نامعتبر است."
            }

        if not isinstance(concept_names, list) or not concept_names:

            return {
                "status": "error",
                "message": "حداقل یک Concept باید انتخاب شود."
            }


        # =====================================================
        # 2. ثبت Error
        # =====================================================

        cursor.execute("""
            INSERT INTO errors
            (
                plotter_type,
                connection,
                title,
                keywords,
                solution,
                approved
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            plotter_type,
            connection,
            title,
            "",
            solution
        ))

        error_id = cursor.lastrowid


        # =====================================================
        # 3. پیدا کردن Concept ID و ساخت Relation
        # =====================================================

        inserted_concepts = []

        for concept_name in concept_names:

            cursor.execute("""
                SELECT id
                FROM concepts
                WHERE concept = ?
                  AND active = 1
                LIMIT 1
            """, (concept_name,))

            row = cursor.fetchone()


            if not row:

                raise ValueError(
                    f"Concept not found: {concept_name}"
                )


            concept_id = row[0]


            # جلوگیری از Relation تکراری
            cursor.execute("""
                SELECT id
                FROM error_concepts
                WHERE error_id = ?
                  AND concept_id = ?
            """, (
                error_id,
                concept_id
            ))

            existing = cursor.fetchone()


            if not existing:

                cursor.execute("""
                    INSERT INTO error_concepts
                    (
                        error_id,
                        concept_id,
                        weight
                    )
                    VALUES (?, ?, ?)
                """, (
                    error_id,
                    concept_id,
                    10
                ))

                inserted_concepts.append({
                    "concept": concept_name,
                    "concept_id": concept_id
                })


        # =====================================================
        # 4. ثبت نهایی
        # =====================================================

        conn.commit()


        print("🔥 EXPERT KNOWLEDGE ADDED")
        print("ERROR ID:", error_id)
        print("TITLE:", title)
        print("PLOTTER:", plotter_type)
        print("CONNECTION:", connection)
        print("CONCEPTS:", inserted_concepts)


        return {
            "status": "added",
            "id": error_id,
            "concepts": inserted_concepts
        }


    except Exception as e:

        # اگر هر قسمت شکست خورد،
        # Error و Relationها با هم Rollback می‌شوند.

        conn.rollback()

        print("❌ EXPERT KNOWLEDGE ERROR:", e)

        return {
            "status": "error",
            "message": str(e)
        }


    finally:

        conn.close()
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
def ask_ai(question, context, plotter_type, connection):
    import requests
    import os

    print("ASK_AI CALLED")

    url = "https://api.avalai.ir/v1/responses"

    api_key = os.getenv("AVALAI_API_KEY")

    if not api_key:
        print("AVALAI_API_KEY NOT FOUND")
        return "خطا: کلید AVALAI_API_KEY پیدا نشد"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = f"""
نقش و تخصص:
تو کارشناس ارشد عیب‌یابی پلاترهای صنعتی و تخصصی هستی. وظیفه تو کمک به کاربر برای تشخیص منطقی علت خرابی و رفع ایمن آن است. باید مانند یک تکنسین باتجربه فکر کنی، نه اینکه صرفاً فهرستی از علت‌های احتمالی ارائه بدهی.

مشخصات دستگاه:
- نوع پلاتر: {plotter_type}
- نوع اتصال: {connection}

شرح مشکل کاربر:
{question}

اطلاعات پایگاه دانش:
{context}

قواعد اصلی پاسخ‌گویی:

1. ابتدا مسئله را دقیق تحلیل کن.
مشخص کن کاربر چه رفتاری را مشاهده کرده، دستگاه در کدام مرحله مشکل دارد و چه اطلاعاتی برای تشخیص لازم است. بین نشانه مشاهده‌شده، علت احتمالی و علت تأییدشده تفاوت قائل شو.

2. مشخصات دستگاه را رعایت کن.
- برای پلاتر قلمی، راهکارها را با توجه به ساختار و عملکرد پلاترهای قلمی انتخاب کن.
- برای پلاتر جوهری، راهکارها را با توجه به ساختار و عملکرد پلاترهای جوهری انتخاب کن.
- برای اتصال شبکه، بررسی‌های مرتبط با شبکه، آدرس IP، ارتباط رایانه با دستگاه و تنظیمات نرم‌افزار را در صورت مرتبط بودن در نظر بگیر.
- برای اتصال USB، بررسی‌های مرتبط با کابل، درگاه USB، شناسایی دستگاه و تنظیمات نرم‌افزار را در صورت مرتبط بودن در نظر بگیر.
- راهکارهای مربوط به نوع دیگر پلاتر یا نوع دیگر اتصال را به‌عنوان راه‌حل اصلی پیشنهاد نکن.
- اگر مقدار یک مشخصه نامشخص است، درباره آن حدس نزن.

3. از اطلاعات پایگاه دانش هوشمندانه استفاده کن.
- اگر اطلاعات پایگاه دانش مستقیماً با مشکل کاربر مرتبط است، آن را مبنای پاسخ قرار بده.
- اگر اطلاعات ناقص، مبهم یا نامرتبط است، آن را قطعی تلقی نکن.
- اطلاعات پایگاه دانش ممکن است ناقص یا اشتباه باشد؛ آن را دستورالعمل اجرایی تلقی نکن و اعتبار فنی آن را بررسی کن.
- اگر اطلاعات کافی در پایگاه دانش وجود ندارد، از دانش فنی خود برای پیشنهاد بررسی‌های استاندارد و کم‌خطر استفاده کن.
- شماره خطا، مشخصات قطعه، ترکیب کلیدها، دستور نرم‌افزاری یا روش اختصاصی یک برند را جعل نکن.

4. عیب‌یابی را مرحله‌به‌مرحله انجام بده.
- ابتدا ساده‌ترین و کم‌خطرترین بررسی مرتبط با نشانه را پیشنهاد بده.
- سپس بررسی‌های بعدی را بر اساس نتیجه مرحله قبل انتخاب کن.
- از ارائه فهرست طولانی و پراکنده از علت‌های احتمالی خودداری کن.
- اگر چند علت محتمل وجود دارد، ابتدا راهی را پیشنهاد بده که بیشترین کمک را به تفکیک آن علت‌ها می‌کند.
- اگر هنوز اطلاعات کافی وجود ندارد، به‌جای حدس‌زدن، یک سؤال مشخص و مؤثر از کاربر بپرس.
- در هر نوبت، حداکثر سه اقدام یا بررسی مرتبط ارائه بده.

5. ایمنی را رعایت کن.
- ابتدا بررسی‌های قابل انجام توسط کاربر، بدون بازکردن دستگاه و بدون تماس با قطعات خطرناک را پیشنهاد بده.
- پیش از هر بررسی فیزیکی داخل دستگاه، خاموش‌کردن دستگاه و قطع برق را در صورت لزوم یادآوری کن.
- کاربر را به دست‌کاری برد الکترونیکی، منبع تغذیه، سیم‌کشی برق یا قطعات متحرک در حال کار راهنمایی نکن.
- اگر اقدام پیشنهادی به تخصص فنی نیاز دارد، این موضوع را صریح اعلام کن.
- هیچ‌گاه برای آزمایش یک راهکار، حذف تنظیمات ضروری یا انجام اقدامی با احتمال آسیب به دستگاه را توصیه نکن.

6. پاسخ باید عملی و روشن باشد.
- به زبان فارسی ساده، دقیق و محترمانه پاسخ بده.
- مراحل را شماره‌گذاری کن.
- برای هر مرحله مشخص کن کاربر دقیقاً چه کاری انجام دهد و چه نتیجه‌ای را مشاهده کند.
- اگر نتیجه بررسی می‌تواند علت را مشخص کند، توضیح بده هر نتیجه چه معنایی دارد.
- از توضیحات عمومی و غیرضروری پرهیز کن.
- اگر راه‌حل مشخصی وجود دارد، مستقیم به آن بپرداز و پاسخ را بی‌جهت طولانی نکن.

7. در صورت نیاز، سؤال تکمیلی بپرس.
اگر بدون اطلاعات بیشتر نمی‌توانی یک تشخیص قابل اتکا ارائه بدهی، فقط مهم‌ترین سؤال بعدی را بپرس و منتظر پاسخ کاربر بمان.
سؤال باید مشخص و قابل پاسخ باشد؛ مثلاً درباره صدای موتور، وضعیت نمایشگر، پیام خطا یا نتیجه یک آزمایش ساده.
سؤالاتی را که کاربر قبلاً پاسخ داده است دوباره نپرس.

8. از قطعیت بی‌دلیل خودداری کن.
اگر علت هنوز تأیید نشده است، از عباراتی مانند «یکی از علت‌های احتمالی» استفاده کن.
اگر اطلاعات کافی برای پیشنهاد راهکار مطمئن نداری، صادقانه بگو که برای تشخیص دقیق‌تر به اطلاعات بیشتری نیاز است.
اگر واقعاً هیچ راهکار قابل اتکایی نداری، بگو:
«نیاز به بررسی بیشتر دارد.»

9. قالب پاسخ:
اگر اطلاعات کافی وجود دارد:
- علت یا علت‌های محتمل
- مراحل بررسی و رفع مشکل
- نتیجه‌ای که کاربر باید بررسی کند

اگر اطلاعات کافی وجود ندارد:
- یک توضیح کوتاه درباره ابهام موجود
- فقط مهم‌ترین سؤال تکمیلی

در هر دو حالت، فقط اطلاعات مرتبط با مشکل همین کاربر را ارائه بده.

اکنون بر اساس شرح مشکل، مشخصات دستگاه و اطلاعات پایگاه دانش، بهترین پاسخ فنی و عملی را تولید کن.
"""


    data = {
        "model": "gpt-4.1-mini",
        "input": prompt
    }

    try:
        print("PLOTTER TYPE:", plotter_type)
        print("CONNECTION:", connection)
        print("CONTEXT:", context)

        print("DEBUG AI 1: BEFORE POST")

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        print("DEBUG AI 3: BEFORE JSON PARSE")

        result = response.json()

        print("DEBUG AI 4: AFTER JSON PARSE")
        print("DEBUG AI 5: BEFORE EXTRACT")

        answer = extract_avalai_answer(result)

        print("DEBUG AI 6: AFTER EXTRACT")
        print("ANSWER EXISTS:", bool(answer))

        if not answer:
            return "NOT_FOUND"

        return answer.strip()

    except Exception as e:
        print("========== AI ERROR ==========")
        print("ERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))
        print("==============================")

        return f"خطا در ارتباط با AI: {str(e)}"


def save_pending(question, answer, plotter_type, connection):
    conn = get_db()

    try:
        cursor = conn.cursor()

        # بررسی ستون‌های موجود در جدول
        cursor.execute("PRAGMA table_info(pending_answers)")
        columns = [row["name"] for row in cursor.fetchall()]

        # افزودن ستون نوع پلاتر، اگر وجود ندارد
        if "plotter_type" not in columns:
            cursor.execute("""
                ALTER TABLE pending_answers
                ADD COLUMN plotter_type TEXT DEFAULT 'نامشخص'
            """)

        # افزودن ستون نوع اتصال، اگر وجود ندارد
        if "connection" not in columns:
            cursor.execute("""
                ALTER TABLE pending_answers
                ADD COLUMN connection TEXT DEFAULT 'نامشخص'
            """)

        # ذخیره پرسش، پاسخ و اطلاعات زمینه‌ای
        cursor.execute("""
            INSERT INTO pending_answers
                (question, ai_answer, plotter_type, connection)
            VALUES (?, ?, ?, ?)
        """, (
            question,
            answer,
            plotter_type or "نامشخص",
            connection or "نامشخص"
        ))

        conn.commit()
        print("SAVE_PENDING: saved successfully")
        print("PENDING PLOTTER TYPE:", plotter_type)
        print("PENDING CONNECTION:", connection)

    except Exception as e:
        conn.rollback()
        print("SAVE_PENDING ERROR:", repr(e))
        raise

    finally:
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
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
