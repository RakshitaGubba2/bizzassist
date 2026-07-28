import json
import logging
import re
from datetime import date

from flask import current_app

from .app_services import get_gemma
from .language_manager import (
    SUPPORTED_LANGUAGES,
    detect_language_from_text,
    normalize_language_code,
)
from .local_fallback_translations import get_local_fallback

logger = logging.getLogger(__name__)


def normalize_assistant_question(text):
    if text is None:
        return ""
    s = str(text).strip().lower()
    for ch in ("\u2019", "\u2018", "\u201c", "\u201d", "`"):
        s = s.replace(ch, "'")
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def assistant_reset_welcome(language="en"):
    return get_local_fallback(language, (
        "Hello! I can answer the 30 built-in questions without any API key. "
        "For other topics, add an NVIDIA NIM API key in Settings or the environment."
    )) or (
        "Hello! I can answer the 30 built-in questions without any API key. "
        "For other topics, add an NVIDIA NIM API key in Settings or the environment."
    )


def localized_fallback_response(language):
    fallbacks = {
        "en": "I can help with your business questions. Ask about inventory, orders, finance, or marketing.",
        "hi": "मैं आपके बिज़नेस सवालों में मदद कर सकता हूँ। स्टॉक, ऑर्डर, वित्त या मार्केटिंग के बारे में पूछें।",
        "te": "మీ వ్యాపార ప్రశ్నలకు నేను సహాయం చేయగలను. స్టాక్, ఆర్డర్లు, ఫైనాన్స్ లేదా మార్కెటింగ్ గురించి అడగండి.",
        "ta": "உங்கள் வணிக கேள்விகளுக்கு நான் உதவ முடியும். இருப்பு, ஆர்டர்கள், நிதி அல்லது மார்க்கெட்டிங் பற்றி கேளுங்கள்.",
        "kn": "ನಾನು ನಿಮ್ಮ ವ್ಯಾಪಾರದ ಪ್ರಶ್ನೆಗಳಿಗೆ ಸಹಾಯ ಮಾಡಬಹುದು. ಇನ್‌ವೆಂಟರಿ, ಆರ್ಡರ್‌ಗಳು, ಹಣಕಾಸು ಅಥವಾ ಮಾರ್ಕೆಟಿಂಗ್ ಬಗ್ಗೆ ಕೇಳಿ.",
        "ml": "ഞാൻ നിങ്ങളുടെ വാണിജ്യ ചോദ്യങ്ങളിൽ സഹായിക്കാം. സ്റ്റോക്ക്, ഓർഡറുകൾ, ധനകാര്യങ്ങൾ അല്ലെങ്കിൽ മാർക്കറ്റിംഗ് സംബന്ധിച്ച് ചോദിക്കൂ.",
        "mr": "मी आपल्या व्यवसायाच्या प्रश्नांमध्ये मदत करू शकतो. साठा, ऑर्डर, अर्थसंकल्प किंवा विपणनाबद्दल विचारा.",
        "gu": "હું તમારા બિઝનેસ પ્રશ્નોમાં મદદ કરી શકું છું. ઇન્વેન્ટરી, ઓર્ડર, નાણાકીય અથવા માર્કેટિંગ વિશે પૂછો.",
        "bn": "আমি আপনার ব্যবসায় সম্পর্কিত প্রশ্নে সহায়তা করতে পারি। স্টক, অর্ডার, বাণিজ্য বা বিপণনের বিষয়ে জিজ্ঞাসা করুন।",
    }
    return fallbacks.get(normalize_language_code(language), fallbacks["en"])


def build_ai_context(conn):
    metrics = query_metrics(conn)
    profile = get_business_profile(conn)
    recent_financials = conn.execute(
        "SELECT year_month, revenue, expenses FROM monthly_financials ORDER BY year_month DESC LIMIT 3"
    ).fetchall()
    financial_lines = "; ".join(
        [f"{row['year_month']}: revenue {row['revenue'] or 0}, expenses {row['expenses'] or 0}" for row in recent_financials]
    )
    return {
        "profile": dict(profile) if profile else {},
        "metrics": metrics,
        "recent_financials": financial_lines,
    }


def query_metrics(conn):
    profile = get_business_profile(conn)
    baseline_revenue = profile["monthly_revenue"] if profile else 0
    baseline_expenses = profile["monthly_expenses"] if profile else 0
    marketing_spend = profile["marketing_spend"] if profile else 0

    revenue_from_orders = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0]
    expenses_from_records = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
    revenue = max(revenue_from_orders, baseline_revenue)
    expenses = max(expenses_from_records, baseline_expenses + marketing_spend)
    net_profit = revenue - expenses
    active_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status IN ('Pending', 'Processing', 'Shipped')"
    ).fetchone()[0]
    low_stock = conn.execute(
        "SELECT COUNT(*) FROM inventory_products WHERE stock <= reorder_level"
    ).fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    vip_customers = conn.execute(
        "SELECT COUNT(*) FROM customers WHERE segment = 'VIP'"
    ).fetchone()[0]
    avg_customer_value = conn.execute(
        "SELECT COALESCE(AVG(total_spent), 0) FROM customers"
    ).fetchone()[0]
    inventory_value = conn.execute(
        "SELECT COALESCE(SUM(price * stock), 0) FROM inventory_products"
    ).fetchone()[0]
    return {
        "revenue": revenue,
        "expenses": expenses,
        "net_profit": net_profit,
        "active_orders": active_orders,
        "low_stock": low_stock,
        "total_customers": total_customers,
        "vip_customers": vip_customers,
        "avg_customer_value": avg_customer_value,
        "inventory_value": inventory_value,
    }


def get_business_profile(conn):
    return conn.execute("SELECT * FROM business_profile WHERE id = 1").fetchone()


def run_gemma_prompt(user_message, reply_language, context):
    gemma = get_gemma()
    if not gemma.is_ready():
        raise RuntimeError("NVIDIA NIM API key is missing")

    reply_language = normalize_language_code(reply_language)
    input_language = detect_language_from_text(user_message, reply_language)
    reply_name = SUPPORTED_LANGUAGES.get(reply_language, "English")
    input_name = SUPPORTED_LANGUAGES.get(input_language, "English")

    prompt = (
        "You are a friendly business assistant for BizAssist AI.\n"
        f"The user message may be in {input_name}. Understand it regardless of language.\n"
        f"You MUST reply ONLY in {reply_name}. Never reply in English unless {reply_name} is English.\n"
        "Use the business context below to answer questions about inventory, sales, finance, marketing, customers, or store management.\n"
        "If the user asked for a business action, describe the result clearly and naturally.\n"
        "Keep answers concise and practical.\n\n"
        f"Business context:\n{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
        f"User message:\n{user_message}"
    )
    logger.info("Gemma request: input_language=%s reply_language=%s prompt=%s", input_language, reply_language, prompt[:2000])
    return gemma.generate_text(prompt, max_output_tokens=1024)


def extract_action(user_message):
    """Keep mutations explicit; ordinary questions require one NIM call only.

    The previous implementation made a second model request before every
    response merely to guess an intent.  Besides doubling latency, a timeout
    there made the assistant appear to send without replying.  Business data
    is still included in the single answer prompt; write actions can be added
    through explicit authenticated commands instead of model guesswork.
    """
    return {"action": "none"}


def perform_business_action(conn, action_data):
    action = action_data.get("action", "none")
    if action == "add_stock":
        item = action_data.get("item") or "Item"
        qty = max(0, int(action_data.get("quantity") or 0))
        if qty <= 0:
            return "I heard a restock request, but could not determine the quantity."
        match = conn.execute(
            "SELECT * FROM inventory_products WHERE lower(name) LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{item.lower()}%",),
        ).fetchone()
        now = date.today().isoformat()
        if match:
            conn.execute(
                "UPDATE inventory_products SET stock = stock + ?, last_restocked = ? WHERE id = ?",
                (qty, now, match["id"]),
            )
            return f"Updated inventory: added {qty} units to {match['name']}."
        conn.execute(
            "INSERT INTO inventory_products (name, sku, category, stock, reorder_level, price, last_restocked) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item, "AUTO-001", "Misc", qty, qty, 0, now),
        )
        return f"Created a new inventory item '{item}' and added {qty} units."

    if action == "show_low_stock":
        rows = conn.execute(
            "SELECT name, stock, reorder_level FROM inventory_products WHERE stock <= reorder_level ORDER BY stock ASC"
        ).fetchall()
        if not rows:
            return "All inventory items are above their reorder thresholds right now."
        return "Low stock items: " + ", ".join(
            [f"{row['name']} ({row['stock']} left, reorder at {row['reorder_level']})" for row in rows]
        )

    if action == "profit_summary":
        metrics = query_metrics(conn)
        return (
            f"Revenue is {metrics['revenue']:.2f}, expenses are {metrics['expenses']:.2f}, "
            f"and net profit is {metrics['net_profit']:.2f}."
        )

    if action == "show_customer_history":
        name = action_data.get("customer_name") or ""
        if not name:
            return "Please tell me which customer you'd like history for."
        row = conn.execute(
            "SELECT * FROM customers WHERE lower(name) LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{name.lower()}%",),
        ).fetchone()
        if not row:
            return f"No customer history found for '{name}'."
        return (
            f"Customer {row['name']} has placed {row['total_orders']} orders, spent {row['total_spent']:.2f}, "
            f"and last purchased on {row['last_purchase']}."
        )

    if action == "create_marketing_campaign":
        title = action_data.get("campaign_title") or "New Campaign"
        description = action_data.get("campaign_description") or "Generated campaign idea from your assistant."
        conn.execute(
            "INSERT INTO campaigns (title, description, segment, target_customers, expected_roi, priority, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, description, "VIP", 20, 120, "Medium", "Ready"),
        )
        return f"Created campaign '{title}' and saved it under Marketing."

    return ""


def build_assistant_response(conn, user_message, reply_language="en"):
    action_data = extract_action(user_message)
    context = build_ai_context(conn)
    if action_data.get("action") != "none":
        context["requested_action"] = action_data
    generation_error = None
    try:
        answer = run_gemma_prompt(user_message, reply_language, context)
    except Exception as exc:
        logger.exception("Gemma generation failed")
        answer = None
        generation_error = exc

    action_summary = ""
    if action_data.get("action") != "none":
        action_summary = perform_business_action(conn, action_data)

    if answer:
        return answer
    if action_summary:
        return action_summary
    if generation_error:
        logger.warning("Assistant generation unavailable: %s", generation_error)
        return localized_fallback_response(reply_language)
    return localized_fallback_response(reply_language)
