import json
import requests
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="SEO Brief Generator for Pleo", page_icon="📝", layout="centered")

# --- FETCH KEYS DIRECTLY FROM STREAMLIT SECRETS ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    AHREFS_API_KEY = st.secrets["AHREFS_API_KEY"]
except Exception:
    st.error("⚠️ API keys missing. Please configure GEMINI_API_KEY and AHREFS_API_KEY in your Streamlit Cloud Secrets settings.")
    st.stop()

MODEL_ID = "gemini-2.5-flash"

# --- HEADER & ATTRIBUTION ---
st.title("SEO Brief Generator for Pleo")
st.markdown(
    "Use this app to generate a short SEO brief based on your target keyword. "
    "This app uses Ahrefs and Gemini to analyse what the user is trying to accomplish, "
    "the content formats that are currently winning in search, and the follow-up questions users are likely to ask."
)
st.markdown("Created by [Lidia Infante](https://www.linkedin.com/in/lidiainfante/)")
st.divider()

# --- COUNTRY MAPPING ---
COUNTRY_MAP = {
    "United Kingdom": "gb",
    "Denmark": "dk",
    "Germany": "de",
    "Spain": "es",
    "Sweden": "se",
    "Netherlands": "nl"
}

# --- RICH RESULT GUIDANCE RULES ---
RICH_RESULT_GUIDANCE = {
    "AI Overview": {
        True: "Google triggers an AI summary for this search. Include a section early in the article that directly answers this prompt and improves upon existing snippets.",
        False: "This search doesn't trigger an AI summary from Google."
    },
    "Image pack": {
        True: "Users need visual aid to fulfill intent. Plan for a custom graphic, diagram, or dataset visualization.",
        False: "Users aren't looking for image features in this search."
    },
    "Video": {
        True: "Users find video content helpful for this topic. Consider embedding a video or short demo.",
        False: "Users aren't looking for video features in this search."
    }
}

class SEOBriefApp:
    def __init__(self, gemini_key, ahrefs_key, model):
        self.gemini_key = gemini_key
        self.ahrefs_key = ahrefs_key
        self.model_id = model
        self.client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None

    def _safe_ai(self, prompt, is_json=False):
        if not self.client:
            return None
        cfg = types.GenerateContentConfig(response_mime_type='application/json' if is_json else 'text/plain')
        try:
            return self.client.models.generate_content(model=self.model_id, contents=prompt, config=cfg).text
        except Exception:
            return None

    def get_query_fanout(self, keyword):
        prompt = (
            f"You are simulating Google's AI Mode query fan-out for generative search systems.\n"
            f"Original Query: \"{keyword}\".\n\n"
            f"Generate 8 unique synthetic queries (AI Queries). You MUST represent each of the following "
            f"transformation types at least once: Reformulations, Related Queries, Implicit Queries, "
            f"Comparative Queries, Entity Expansions, and Personalized Queries.\n\n"
            f"Return ONLY valid JSON: {{ \"fanout\": [\"query1\", \"query2\", ...] }}"
        )
        res = self._safe_ai(prompt, is_json=True)
        try:
            return json.loads(res).get('fanout', [])
        except Exception:
            return []

    def get_reward_sentence(self, valid_page_types):
        types_list_str = ", ".join(sorted(list(set(valid_page_types)))) if valid_page_types else "varied"
        prompt = (
            f"DATA: The following Ahrefs Page Types were detected ranking in the Top 10: [{types_list_str}]\n\n"
            f"TASK: Generate a single natural, insightful sentence explaining what type of pages are ranking on Google for this intent.\n"
            f"Example: 'The pages ranking for this query are informational guides, step-by-step how-to's and some thought leadership.'\n\n"
            f"Return ONLY the plain text sentence."
        )
        return self._safe_ai(prompt) or "Search results overview could not be generated."

    def get_search_intent(self, keyword, secondary_kws, serp_summary, reward_sentence):
        base_instr = (
            "Provide a concise one-sentence description of what the user is trying to achieve. "
            "DO NOT include any labels, prefixes, or bold text like 'Job to be Done:' or 'Intent:'. "
            "Start the sentence directly with a verb."
        )
        if secondary_kws:
            prompt = f"Analyze intent for: '{keyword}' with context from '{', '.join(secondary_kws)}'.\nSERP:\n{serp_summary}\nReward: {reward_sentence}\nInstructions: {base_instr}\nIntent:"
        else:
            prompt = f"Analyze intent for: '{keyword}'.\nSERP:\n{serp_summary}\nReward: {reward_sentence}\nInstructions: {base_instr}\nIntent:"

        res = self._safe_ai(prompt)
        raw_intent = (res or "explore topic for information.").strip().replace("**Job to be Done:**", "").replace("Job to be Done:", "").strip()
        
        if raw_intent and raw_intent[0].isupper():
            raw_intent = raw_intent[0].lower() + raw_intent[1:]
        return raw_intent

    def get_bulk_volumes(self, keywords, country_code):
        headers = {"Authorization": f"Bearer {self.ahrefs_key}", "Accept": "application/json"}
        url = "https://api.ahrefs.com/v3/keywords-explorer/overview"
        params = {"keywords": ",".join(keywords), "country": country_code, "select": "keyword,volume"}
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            return {item['keyword'].lower().strip(): item.get('volume', 0) for item in res.json().get('keywords', [])}
        except Exception:
            return {}

    def run_analysis(self, keyword, secondary_kws, country_code, status_container):
        status_container.update(label=f"🔍 Scanning Google SERP ({country_code.upper()})...", state="running")
        headers = {"Authorization": f"Bearer {self.ahrefs_key}", "Accept": "application/json"}
        serp_url = "https://api.ahrefs.com/v3/serp-overview/serp-overview"
        serp_params = {"keyword": keyword, "country": country_code, "select": "type,title,page_type"}

        try:
            serp_res = requests.get(serp_url, params=serp_params, headers=headers, timeout=15)
            data = serp_res.json()
        except Exception as e:
            return None, f"Ahrefs Connection Failed: {str(e)}"

        positions = data.get('positions', [])
        hints, organic_types, paa = [], [], []
        features = {"AI Overview": False, "Image pack": False, "Video": False}
        nav_noise = ["login", "sign up", "careers", "privacy policy", "homepage", "contact us"]

        for pos in positions:
            t = pos.get('type', [])
            title = pos.get('title')

            if title is None: continue
            if any(n in title.lower() for n in nav_noise): continue
            if "ai_overview_sitelink" in t: continue

            if len(hints) < 12:
                hints.append(f"Title: {title} | Type: {pos.get('page_type', 'organic')}")

            if "question" in t: paa.append(title)
            if "ai_overview" in t: features["AI Overview"] = True
            if any(x in t for x in ["image_pack", "image_th"]): features["Image pack"] = True
            if any(x in t for x in ["video", "video_th"]): features["Video"] = True
            if pos.get('page_type') and "organic" in t: organic_types.append(pos.get('page_type'))

        status_container.update(label="📊 Pulling Data & AI Insights...", state="running")
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_vols = executor.submit(self.get_bulk_volumes, [keyword] + secondary_kws, country_code)
            future_fanout = executor.submit(self.get_query_fanout, keyword)
            reward = self.get_reward_sentence(organic_types)
            intent = self.get_search_intent(keyword, secondary_kws, "\n".join(hints), reward)
            vols = future_vols.result()
            fanout = future_fanout.result()

        status_container.update(label="✅ Analysis Complete.", state="complete")
        return {"intent": intent, "reward": reward, "fanout": fanout, "paa": paa, "features": features, "volumes": vols}, None


# --- USER INPUT FORM ---
with st.form("brief_form"):
    main_kw = st.text_input("Insert your main keyword here", value="ai in finance")
    
    selected_country = st.selectbox(
        "Target Market",
        options=list(COUNTRY_MAP.keys()),
        index=0
    )
    
    with st.expander("Optional: Add secondary keywords"):
        sec_kws_input = st.text_input("Secondary keywords (comma-separated)", placeholder="pricing, competitors")

    submitted = st.form_submit_button("Generate SEO Brief", type="primary")

# --- EXECUTION & OUTPUT ---
if submitted:
    if not main_kw.strip():
        st.error("Please insert a main keyword.")
    else:
        country_code = COUNTRY_MAP[selected_country]
        sec_kws = [x.strip() for x in sec_kws_input.split(",") if x.strip()]
        app = SEOBriefApp(GEMINI_API_KEY, AHREFS_API_KEY, MODEL_ID)

        status_box = st.status("Initializing analysis...", expanded=True)

        res, err = app.run_analysis(main_kw.strip(), sec_kws, country_code, status_box)

        if err:
            st.error(f"❌ {err}")
        else:
            vols = res['volumes']
            raw_vol = vols.get(main_kw.strip().lower(), "N/A")
            formatted_vol = f"{raw_vol:,}" if isinstance(raw_vol, int) else str(raw_vol)

            # Build Rich Results section lines
            rich_results_lines = []
            for feat_name, is_present in res['features'].items():
                icon = "✅" if is_present else "❌"
                guidance = RICH_RESULT_GUIDANCE.get(feat_name, {}).get(is_present, "")
                rich_results_lines.append(f"- **{feat_name}** {icon} — {guidance}")
            rich_results_block = "\n".join(rich_results_lines)

            # Build PAA lines
            paa_lines = "\n".join([f"- {q}" for q in res['paa'][:5]]) if res['paa'] else "- None detected"

            # Build Fanout lines
            fanout_lines = "\n".join([f"- {q}" for q in res['fanout']]) if res['fanout'] else "- None generated"

            st.divider()

            # FORMATTED BRIEF WITH ARROW BULLETS AND BREAKS
            brief_output = (
                f"**Main keyword:** {main_kw.strip()} — {formatted_vol} monthly searches ({selected_country})\n\n"
                f"**What is the user trying to accomplish?**\n\n"
                f"➡️ The user is trying to {res['intent']}\n\n"
                f"**What's currently winning on Google?** Use this information to inform how to satisfy the search intent of your reader.\n\n"
                f"➡️ {res['reward']}\n\n"
                f"**Rich results on Google:**\n\n"
                f"{rich_results_block}\n\n"
                f"❓ **Questions that the user might be trying to answer:** Use these to understand more about the users' pain points and emotional state. You can answer these in your content if they are relevant.\n\n"
                f"{paa_lines}\n\n"
                f"🔮 **Deep dive questions:** These are some of the potential follow-ups the user might ask an LLM. Use these to help your reader finish the journey:\n\n"
                f"{fanout_lines}"
            )

            st.markdown(brief_output)