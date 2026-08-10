import sqlite3

def normalize_concept(text):
    text = str(text)
    text = text.lower()

    # یکسان‌سازی حروف عربی و فارسی
    text = text.replace("ي", "ی")
    text = text.replace("ى", "ی")
    text = text.replace("ك", "ک")

    # یکسان‌سازی نیم‌فاصله
    text = text.replace("‌", " ")

    # حذف فاصله‌های اضافی
    text = " ".join(text.split())

    return text.strip()
def calculate_score(user_text, keywords):
    score = 0

    user_text = normalize_concept(user_text)

    # برای مقایسه، فاصله‌ها و نیم‌فاصله‌ها را حذف می‌کنیم
    user_compact = user_text.replace(" ", "")

    user_words = set(user_text.split())

    for k in keywords:

        if not k:
            continue

        k = normalize_concept(k)

        k_compact = k.replace(" ", "")
        keyword_words = set(k.split())

        # 1. تطبیق کامل
        if k == user_text:
            score += 5
            print("🎯 EXACT MATCH:", k)

        # 2. تطبیق کامل بدون توجه به فاصله/نیم‌فاصله
        elif k_compact == user_compact:
            score += 5
            print("🎯 COMPACT MATCH:", k)

        # 3. عبارت کلیدی کامل داخل سؤال
        elif k_compact in user_compact:
            score += 3
            print("🎯 PHRASE MATCH:", k)

        # 4. کلمات مشترک
        else:
            common = user_words & keyword_words

            if common:
                score += len(common)
                print("🔹 COMMON WORDS:", common)

    return score


def search_solution(user_text, plotter_type, connection):
    conn = sqlite3.connect("errors.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, solution, keywords
        FROM errors
        WHERE approved = 1
        AND (plotter_type = ? OR plotter_type = 'نامشخص')
        AND (connection = ? OR connection = 'نامشخص')
    """, (plotter_type, connection))

    rows = cursor.fetchall()

    results = []

    for title, solution, keywords in rows:
        keyword_list = [
            k.strip() for k in keywords.replace("،", ",").split(",")
            if k.strip()
        ]

        score = calculate_score(user_text, keyword_list)

        print(f"🔥 SEARCH: {title} SCORE: {score}")

        if score > 0:
            results.append({
                "score": score,
                "title": title,
                "solution": solution
            })

    conn.close()

    if not results:
        return {"type": "ai"}

    results.sort(key=lambda x: x["score"], reverse=True)

    top1 = results[0]
    top2 = results[1] if len(results) > 1 else {"score": 0}

    score1 = top1["score"]
    score2 = top2["score"]

    print(f"✅ DATABASE MATCH: {top1['title']}")
    print(f"✅ SCORE: {score1}")

    if score1 >= 5 and (score1 - score2) >= 2:
        print("✅ HIGH CONFIDENCE (DB)")
        print("✅ SCORE:", score1)
        print("✅ DIFFERENCE:", score1 - score2)

        return {
         "type": "db",
         "data": top1
    }

    elif score1 >= 5:
        print("⚠️ MEDIUM CONFIDENCE (DB)")
        print("⚠️ SCORE:", score1)
        print("⚠️ DIFFERENCE:", score1 - score2)

        return {
            "type": "hybrid",
            "data": top1
    }

    else:
        print("❌ LOW CONFIDENCE (AI)")
        print("❌ SCORE:", score1)

        return {
            "type": "ai"
    }