# מבנה ומדריך לקוד ה-Backend של FDS AI Platform

מדריך זה מספק פירוט טכני מעמיק על תיקיות וקבצי ה-Backend, ומסביר את מחזור החיים של בקשת משתמש בתוך המערכת.

---

## 1. מבנה התיקיות ב-`backend/app/`

הקוד ב-Backend בנוי לפי עקרונות **Clean Architecture**, מה שמאפשר הפרדה ברורה בין הלוגיקה העסקית לתשתית הטכנית.

### `application/agents/` (לוגיקה עסקית - סוכני ה-AI)
זוהי התיקיה המרכזית שמנהלת את ה-Workflow.
- **`router_agent.py`**: נקודת הכניסה. מנתח את שאילתת המשתמש ומסווג אותה לאחד מ-4 סוגי Intents: `single_doc_chat`, `cross_doc_chat`, `compare_documents`, `executive_summary`.
- **`retrieval_agent.py`**: מבצע את תהליך ה-RAG. שולף מידע רלוונטי ממסד הנתונים הוקטורי (Pinecone) לפי השאילתה, מדרג מחדש (Rerank) ומרחיב את ההקשר (Parent Chunks).
- **`comparison_agent.py`**: מנתח שני מסמכים ומפיק דוח השוואה מובנה (`match`, `diff`, `missing`). משתמש ב-Smart Tier (מודל חזק).
- **`summary_agent.py`**: מפיק סיכום מנהלים. מדרג שינויים לפי חשיבות עסקית (ולא לפי סדר כרונולוגי).
- **`validation_agent.py`**: סוכן אבטחה ואיכות. בודק אם התשובה שהופקה מבוססת עובדתית על המקורות (Grounding) כדי למנוע הזיות.
- **`response_agent.py`**: מגבש את התשובה הסופית למשתמש תוך שילוב סימוכין מהקשר השיחה והמסמכים.
- **`citation_agent.py`**: מבצע ניקוי סופי לסימוכין כדי להבטיח שכל ציטוט קיים בתוצאות השליפה.
- **`state.py`**: מגדיר את המבנה של ה-`GraphState` שעובר בין כל הסוכנים ומחזיק את המידע הזמני של הריצה.

### `domain/entities/` (מודלים עסקיים)
- **`document.py`**: מגדיר את ה-Dataclasses שמהווים את השפה העסקית (למשל `ComparisonReport`, `GroundedAnswer`, `DocumentChunk`). אלו אובייקטים טהורים ללא תלות במסדי נתונים או OpenAI.

### `infrastructure/` (תשתית)
- **`ai/openai_client.py`**: עוטף את הקריאות ל-OpenAI (מודלים, Embeddings).
- **`vectordb/pinecone_client.py`**: עוטף את התקשורת עם Pinecone (שליפה ואיחסון וקטורים).

### `core/` (כלים טכניים)
- **`config.py`**: טעינת משתני סביבה (`.env`).
- **`tokens.py`**: לוגיקה לחישוב וקיצוץ טוקנים כדי לעמוד במגבלות התקציב של המודלים.

---

## 2. מחזור חיים של בקשת משתמש (מה-Frontend לבקאנד)

כאשר משתמש שולח שאילתה דרך ה-Frontend, מתרחש התהליך הבא:

1.  **API Gateway (`main.py`)**: הבקשה מגיעה לנקודת הקצה `/api/v1/query`. ה-API מעביר את נתוני המשתמש (שאילתה ו-document_ids) ל-`LangGraph`.
2.  **ניתוב (`Router Agent`)**: המערכת מפעילה את `Router Agent`. הוא קורא את השאילתה ומחליט על ה-Intent (למשל: "השווה בין המסמכים").
3.  **שליפת מידע (`Retrieval Agent`)**:
    *   השאילתה מומרת לוקטור (Embedding).
    *   מתבצע חיפוש ב-Pinecone למציאת `child chunks` רלוונטיים.
    *   הסוכן מבצע `Reranking` לשיפור הרלוונטיות.
    *   הסוכן מרחיב את התוצאות ל-`parent chunks` (הקשר מלא).
4.  **ביצוע המשימה (`Task Agent`)**: לפי ה-Intent מהשלב הראשון, המערכת מריצה סוכן ספציפי:
    *   אם השוואה: `Comparison Agent` מנתח את ה-`expanded_context` ומחזיר מבנה JSON קשיח.
    *   אם סיכום: `Summary Agent` מדרג את השינויים ומפיק סיכום מנהלים.
    *   אם צ'אט: `Response Agent` מנסח תשובה.
5.  **תיקוף (`Validation Agent`)**: לפני שהתשובה נשלחת למשתמש, `Validation Agent` עובר על התשובה ועל המקורות (`retrieved_chunks`). אם הוא מזהה טענה שאין לה ביסוס במסמכים (הזיה), הוא מסמן `is_grounded: false`.
6.  **חזרה למשתמש**: המערכת מחזירה את התשובה (או הודעת "מידע חסר") ל-Frontend, עם הציטוטים המדויקים שנבדקו ע"י `Citation Agent`.
