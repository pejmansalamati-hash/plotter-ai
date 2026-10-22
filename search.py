print("✅ SEARCH.PY V2.3 LOADED")

import sqlite3
import re


# =====================================================
# DATABASE
# =====================================================


import os

DB_NAME = "/data/errors.db"


# =====================================================
# NORMALIZATION
# =====================================================

def normalize(text):

    if text is None:
        return ""

    text = str(text).lower()

    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")

    text = text.replace("‌", " ")

    text = " ".join(text.split())

    return text.strip()


# =====================================================
# LOAD CONCEPTS
# =====================================================

def load_concepts():

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""

        SELECT
            concept,
            synonym,
            weight,
            category,
            active

        FROM concepts

        WHERE active = 1

    """).fetchall()
    print("ROWS COUNT:", len(rows))

    for row in rows:
        print("LOADED ROW:", dict(row))
    conn.close()

    return rows


CONCEPTS = load_concepts()


# =====================================================
# NORMALIZE CONCEPT
# =====================================================

def normalize_concept(text):

    text = normalize(text)

    for row in CONCEPTS:

        synonym = normalize(row["synonym"])
        concept = normalize(row["concept"])

        text = text.replace(
            synonym,
            concept
        )

    return text


# =====================================================
# STOP WORDS
# =====================================================

STOP_WORDS = {

    "است",
    "شد",
    "شده",

    "می",
    "نمی",
    "شود",

    "کرد",
    "کند",

    "برای",
    "با",
    "در",
    "از",
    "به",

    "و",
    "یا",
    "را",
    "که",

    "این",
    "آن",

    "دستگاه",
    "پلاتر",

}


# =====================================================
# TOKENIZER
# =====================================================

def get_words(text):

    text = normalize(text)

    words = re.findall(
        r"[\u0600-\u06FF]+",
        text
    )

    return {

        word

        for word in words

        if len(word) >= 2

    }


def get_important_words(text):

    return {

        word

        for word in get_words(text)

        if word not in STOP_WORDS

    }
# =====================================================
# MULTI CONCEPT DETECTOR
# =====================================================

def detect_concepts(user_text):

    # =============================================
    # NORMALIZE USER TEXT
    # =============================================

    text = normalize_concept(user_text)

    # برای جستجوی synonym، متن اصلی را نگه می‌داریم
    original_text = user_text

    detected = []

    # =============================================
    # LOAD CONCEPTS
    # =============================================

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            concept,
            synonym,
            weight,
            category,
            active
        FROM concepts
        WHERE active=1
        ORDER BY weight DESC
    """).fetchall()

    conn.close()

    # از هر category فقط یک مفهوم
    used_categories = set()

    # =============================================
    # NORMALIZE FOR MATCHING
    # =============================================

    def normalize_match(value):

        if not value:
            return ""

        value = str(value)

        # تبدیل نیم‌فاصله به فاصله
        value = value.replace("\u200c", " ")

        # یکسان‌سازی فاصله‌ها
        value = " ".join(value.split())

        # یکسان‌سازی شکل‌های مختلف «می»
        value = value.replace("می ", "می")

        # یکسان‌سازی شکل‌های مختلف «نمی»
        value = value.replace("نمی ", "نمی")

        # حذف فاصله برای ساخت نسخه دوم
        compact = value.replace(" ", "")

        return value, compact

    search_normalized, search_compact = normalize_match(original_text)

    # =============================================
    # CHECK CONCEPTS
    # =============================================

    for row in rows:

        synonym = row["synonym"]

        if not synonym:
            continue

        synonym_normalized, synonym_compact = normalize_match(
            synonym
        )

        matched = False

        # =========================================
        # MULTI-WORD SYNONYM
        # =========================================

        if " " in synonym_normalized:

            # مثال:
            # صدای تق تق
            # چاپ نمی کند
            # روشن نمی شود

            if synonym_normalized in search_normalized:
                matched = True

            # نسخه بدون فاصله
            elif synonym_compact in search_compact:
                matched = True

        # =========================================
        # SINGLE-WORD SYNONYM
        # =========================================

        else:

            # کلمات متن را جدا می‌کنیم
            words = search_normalized.split()

            # -----------------------------------------
            # حالت عادی
            # -----------------------------------------

            if synonym_normalized in words:
                matched = True

            # -----------------------------------------
            # جلوگیری از false match
            #
            # مثال:
            # synonym = کند
            #
            # نباید در:
            # نمی‌کند
            #
            # پیدا شود.
            # -----------------------------------------

            if synonym_normalized == "کند":

                blocked_words = {
                    "نمی‌کند",
                    "نمی کند",
                    "نمیکند",
                    "نمی‌كند",
                    "نمی كند"
                }

                for blocked in blocked_words:

                    if blocked in original_text:
                        matched = False
                        break

        # =========================================
        # DEBUG
        # =========================================

        print(
            "CHECK:",
            row["concept"],
            "| SYNONYM:",
            row["synonym"],
            "->",
            matched
        )

        if not matched:
            continue

        category = row["category"]

        # =========================================
        # ONE CONCEPT PER CATEGORY
        # =========================================

        if category in used_categories:
            continue

        detected.append({
            "concept": row["concept"],
            "weight": row["weight"],
            "category": category,
            "synonym": row["synonym"]
        })

        used_categories.add(category)

    return detected
# =====================================================
# TEST MULTI CONCEPT
# =====================================================

def test_detect_concepts():

    test_text = "پلاتر جوهرافشان شبکه روشن نمیشه"

    concepts = detect_concepts(test_text)

    print("===================================")
    print("TEST QUESTION:", test_text)
    print("DETECTED CONCEPTS:")

    for item in concepts:

        print(
            f"➡️ {item['concept']} | "
            f"weight={item['weight']} | "
            f"category={item['category']}"
        )

    print("===================================")

    return concepts
print("🔥 MULTI-CONCEPT TEST")

test_detect_concepts()
# =====================================================
# CALCULATE SCORE (V2.3)
# =====================================================


def calculate_score(
    user_text,
    title,
    concept,
    synonym,
    relation_weight
):
    user_text = normalize(user_text or "")
    title = normalize(title or "")
    concept = normalize(concept or "")
    synonym = normalize(synonym or "")

    user_words = get_important_words(user_text)
    title_words = get_important_words(title)
    synonym_words = get_important_words(synonym)

    score = 0

    # 1. Exact title match
    if title == user_text:
        score += 30
    elif title.replace(" ", "") == user_text.replace(" ", ""):
        score += 25

    # 2. Title word overlap
    common_title = user_words & title_words
    score += len(common_title) * 5

    # 3. Reward matching the more informative title words
    if title_words:
        title_coverage = len(common_title) / len(title_words)
        score += int(title_coverage * 15)

    # 4. Concept synonym match
    common_synonym = user_words & synonym_words
    relation_weight = relation_weight or 0
    score += len(common_synonym) * relation_weight

    print("USER:", user_text)
    print("TITLE:", title)
    print("CONCEPT:", concept)
    print("COMMON TITLE:", common_title)
    print("COMMON SYNONYM:", common_synonym)
    print("REL_WEIGHT:", relation_weight)
    print("FINAL SCORE:", score)

    return score

# =====================================================
# LOAD ERROR ROWS
# =====================================================


def load_error_rows(plotter_type, connection):

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    try:
        print("DB FILE:", DB_NAME)

        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM errors")
        print("ERRORS:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM concepts")
        print("CONCEPTS:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM error_concepts")
        print("ERROR_CONCEPTS:", cursor.fetchone()[0])

        rows = conn.execute("""
            SELECT
                e.id AS error_id,
                e.title,
                e.solution,
                c.concept,
                c.synonym,
                c.weight,
                c.category,
                ec.weight AS relation_weight

            FROM errors e

            LEFT JOIN error_concepts ec
                ON ec.error_id = e.id

            LEFT JOIN concepts c
                ON c.id = ec.concept_id
                AND c.active = 1

            WHERE
                e.approved = 1

                AND (
                    e.plotter_type = ?
                    OR e.plotter_type = 'نامشخص'
                )

                AND (
                    e.connection = ?
                    OR e.connection = 'نامشخص'
                )

            ORDER BY e.id
        """, (plotter_type, connection)).fetchall()

        print("ROWS LOADED:", len(rows))

        for r in rows:
            print(
                r["error_id"],
                r["title"],
                r["concept"],
                r["synonym"],
                r["relation_weight"]
            )

        return rows

    finally:
        conn.close()

# =====================================================
# SEARCH SOLUTION
# =====================================================


def search_solution(user_text, plotter_type, connection):

    print("🔥 SEARCH_SOLUTION RUNNING")

    # ------------------------------------
    # 1. Detect Concepts
    # ------------------------------------

    detected_concepts = detect_concepts(user_text)

    print("=" * 35)
    print("DETECTED CONCEPTS:")

    detected_codes = set()

    for item in detected_concepts:
        print(
            f"➡️ {item['concept']} | "
            f"weight={item['weight']} | "
            f"category={item['category']}"
        )

        detected_codes.add(item["concept"])

    print("=" * 35)

    # ------------------------------------
    # 2. No Concept = Send Directly to AI
    # ------------------------------------

    
    # ------------------------------------
    # 3. Load Database
    # ------------------------------------

    rows = load_error_rows(
        plotter_type,
        connection
    )

    print("PLOTTER_TYPE FROM ASK:", plotter_type)
    print("CONNECTION FROM ASK:", connection)
    print("ROWS LOADED:", len(rows))

    if not rows:
        print("⚠️ NO DATABASE ROWS - ROUTING TO AI")
        return {"type": "ai"}

    results = {}

    # ------------------------------------
    # 4. Score
    # ------------------------------------

    for row in rows:

        score = calculate_score(
            user_text,
            row["title"],
            row["concept"],
            row["synonym"],
            row["relation_weight"]
        )

        # Concept Bonus
        if row["concept"] in detected_codes:
            score += 25

        print(
            f"🔥 {row['error_id']} | "
            f"{row['concept']} | "
            f"{row['synonym']} | "
            f"SCORE={score}"
        )

        error_id = row["error_id"]

        if error_id not in results:
            results[error_id] = {
                "title": row["title"],
                "solution": row["solution"],
                "score": 0
            }

        results[error_id]["score"] += score

    # ------------------------------------
    # 5. Ranking
    # ------------------------------------

    results = list(results.values())

    if not results:
        print("⚠️ NO RESULTS - ROUTING TO AI")
        return {"type": "ai"}

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    top1 = results[0]

    if len(results) > 1:
        top2 = results[1]
    else:
        top2 = {"score": 0}

    score1 = top1["score"]
    score2 = top2["score"]

    print("=" * 35)
    print("BEST MATCH :", top1["title"])
    print("TOP SCORE  :", score1)
    print("SECOND     :", score2)
    print("GAP        :", score1 - score2)
    print("=" * 35)

    # ------------------------------------
    # 6. Reject Zero or Negative Scores
    # ------------------------------------

    if score1 <= 0:
        print("❌ NO POSITIVE MATCH - ROUTING TO AI")
        return {"type": "ai"}

    # ------------------------------------
    # 7. Decision
    # ------------------------------------

    if score1 >= 30 and (score1 - score2) >= 8:

        print("✅ HIGH CONFIDENCE")

        return {
            "type": "db",
            "data": top1
        }

    elif score1 >= 18:

        print("⚠️ MEDIUM CONFIDENCE")

        return {
            "type": "hybrid",
            "data": top1
        }

    else:

        print("❌ LOW CONFIDENCE")
        return {"type": "ai"}
