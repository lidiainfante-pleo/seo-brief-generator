# 📝 SEO Brief Generator for Pleo

An automated, writer-focused SEO brief generator built with **Streamlit**, powered by **Ahrefs API v3** and **Google Gemini (2.5 Flash)**.

Created by [Lidia Infante](https://www.linkedin.com/in/lidiainfante/).

---

## 🎯 Purpose

This app helps SEOs and content strategists quickly generate actionable briefs for content writers. It analyzes real-time SERP data and LLM intent modeling to produce:

1. **User Accomplishment Goal:** Clear description of search intent starting directly with an action verb.
2. **Winning Formats:** A summary of the page types currently ranking in the Top 10.
3. **Rich Results Guidance:** Specific, actionable instructions based on present or absent SERP features (AI Overviews, Image Packs, Videos).
4. **Pain Points & Questions (PAA):** Real user questions from Google SERPs to highlight emotional state and core concerns.
5. **Deep Dive Questions (AI Fanout):** Synthetic queries simulating Google AI Search expansion paths to help readers finish their journey.

---

## 🌍 Supported Target Markets

The app supports target country filtering for Ahrefs volume and SERP data across key Pleo markets:
- 🇬🇧 United Kingdom (`gb`)
- 🇩🇰 Denmark (`dk`)
- 🇩🇪 Germany (`de`)
- 🇪🇸 Spain (`es`)
- 🇸🇪 Sweden (`se`)
- 🇳🇱 Netherlands (`nl`)

---

## 🛠️ Local Setup

1. **Clone or download the repository.**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt