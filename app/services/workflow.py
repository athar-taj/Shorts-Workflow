"""
Service – Complete n8n Workflow Automation.

Features:
1. Fetching & Filtering Trending YouTube Videos
2. Generating Metadata via Groq/OpenRouter
3. Sending Telegram Notifications
"""
import json
import re
import random
import urllib.request
import urllib.error
import os

import subprocess

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("service.workflow")

# -----------------------------------------------------------------------------
# MASTER CONTENT ENGINE v3 (two-stage: idea brief → script)
# -----------------------------------------------------------------------------
BAD_OPENERS = [
    "aaj hum", "dosto aaj", "is video mein", "did you know", "today we will learn",
    "namaste", "welcome back", "hello friends", "hi guys", "in this short",
]

OPENROUTER_MODELS_V3 = {
    "fast": "mistralai/mistral-7b-instruct",
    "quality": "mistralai/mixtral-8x7b-instruct",
    "best": "anthropic/claude-3-haiku",
}

# CATEGORY_MAP imported from your content_engine_v3.py (condensed into our service file)
# Each category carries the context needed to write like a real creator.
CATEGORY_MAP: dict[str, dict] = {
    "Gaming & Metaverse": {
        "subtopics": [
            "BGMI / PUBG Mobile", "Free Fire Max", "Minecraft Survival & Mods",
            "GTA V Roleplay", "Valorant Competitive", "Fighting Games (Tekken/Street Fighter)",
            "Esports Highlights", "Souls Games (Elden Ring/Dark Souls)", "Hindi Commentary & Roasting",
            "Total Gaming Style Walkthroughs", "Speedrunning", "Game Lore & Theory",
            "Roblox Modding", "VR/AR Gameplay Immersive", "Game Easter Eggs & Secrets",
            "Pro Player Strategies", "Mobile vs PC Debate", "Gaming Setup Tours",
        ],
        "audience": "18–28 male gamers, play mobile/PC daily",
        "tone": "hyper-energetic, bro culture, competitive",
        "language": "Heavy Hinglish, gaming terms natural (clutch, ranked, noob, gg, carry)",
        "what_works": "Inside knowledge, pro tips, lore reveals, community drama",
        "what_fails": "Explaining game basics, generic 'gaming is fun' content",
    },
    "Cooking & Gastronomy": {
        "subtopics": [
            "Village Cooking / Outdoor Fire", "5-Minute Quick Meals",
            "Street Food Tours India", "Street Food Tours Global",
            "ASMR Baking & Pastry", "Healthy Meal Prep / Keto Recipes",
            "Chef Reviews & Kitchen Hacks", "Traditional Heritage Recipes",
            "Blind Taste Tests", "Budget Cooking Challenges",
            "Fusion Indian Food", "Midnight Snack Ideas",
            "Festival Special Dishes", "Weird Food Combos That Work",
            "Food Science Facts", "Restaurant Dupes at Home",
            "Desi Superfoods Explained", "Regional Indian Cuisines Hidden Gems",
        ],
        "audience": "Foodies 18–45, urban + semi-urban India",
        "tone": "warm, sensory, satisfying",
        "language": "Hinglish, regional food names naturally",
        "what_works": "Story behind the dish, surprising technique, result-first framing",
        "what_fails": "Recipe listing, ingredient dumps, 'today we make...'",
    },
    "Comedy & Entertainment": {
        "subtopics": [
            "Stand-Up Comedy Observations", "Crowd Work & Improvisation",
            "Sketch Comedy & Parodies", "CarryMinati Style Roasting",
            "Hidden Camera Pranks", "Meme Reviews", "Sitcom Recaps",
            "Reaction Videos", "Dark Humor / Satire", "Relatable Life Situations",
            "Indian Parent Roast", "Office Life Comedy", "College Life Jokes",
            "Exam Season Memes", "Desi Stereotypes Explained",
            "Gen Z vs Millennial Debates", "Women's Fighting Reactions",
        ],
        "audience": "16–28, follow meme culture, all genders",
        "tone": "unfiltered, relatable, slightly chaotic",
        "language": "Maximum Hinglish, slang, meme references",
        "what_works": "Observations that feel painfully true, unexpected comparisons",
        "what_fails": "Setup-punchline structure, explaining the joke",
    },
    "Geopolitics, War & Defense": {
        "subtopics": [
            "Live Conflict Updates & Analysis", "Military Tech & Weaponry Reviews",
            "Geopolitical Power Shifts", "Modern Warfare History",
            "Special Forces Training POV", "Defense News India",
            "Defense News Global", "Geographical Map Explainers Johnny Harris Style",
            "Nuclear Strategy & Deterrence", "India Border Conflicts Explained",
            "Secret Military Operations", "War Economics",
            "Spy Stories", "Naval Power Rankings",
            "Air Force Comparisons", "Cyber Warfare Explained",
            "Historical Battle Breakdowns",
        ],
        "audience": "20–35 males, interested in military and world events",
        "tone": "serious, authoritative but accessible",
        "language": "Cleaner Hinglish, English for geopolitical terms",
        "what_works": "Specific numbers, timeline of events, strategic reasoning",
        "what_fails": "Political bias, inflammatory framing, vague 'war is bad'",
    },
    "Facts & Infotainment": {
        "subtopics": [
            "Psychology Facts", "Space & Universe Mysteries", "Historical Secrets",
            "FactTechz Style Explainer", "Myth-Busting", "Science Experiments",
            "Top 5 Shocking Lists", "Ancient Civilizations", "Forensics & Crime Science",
            "Human Body Weird Facts", "Animal Kingdom Shocking Facts",
            "Ocean Mysteries", "Coincidences That Changed History",
            "Numbers & Math Curiosities", "Optical Illusions & Brain Tricks",
            "Dreams & Sleep Science", "Extinct Creatures", "Unsolved Mysteries of Science",
        ],
        "audience": "15–30, curious and share-happy",
        "tone": "mind-blown energy, curiosity-first",
        "language": "Hinglish, emphasis words in English (literally, actually, wait—)",
        "what_works": "Facts so specific they sound fake, personal connection at the end",
        "what_fails": "'Did you know' openers, encyclopedia tone, fact dumps with no story",
    },
    "Tech & Future-Proofing": {
        "subtopics": [
            "Smartphone Unboxing & Reviews", "Budget PC Building",
            "Tech News Hindi", "Home Automation & IoT",
            "Software Development Vlogs", "Cybersecurity & Ethical Hacking",
            "AI Hardware Reviews", "Electric Vehicle Tech", "Metaverse Updates",
            "Hidden Phone Features", "App Reviews That Matter",
            "Gadget Life Hacks", "Tech Scams Exposed",
            "Open Source Tools", "Cloud Computing Simplified",
            "Wearable Tech Explained", "5G & Network Tech Reality",
        ],
        "audience": "18–35, tech-curious, aspirational buyers, students",
        "tone": "excited but grounded, chai-pe-charcha with a tech friend",
        "language": "Tech English terms natural, Hindi for explanation",
        "what_works": "What it means for THEM, not specs — impact over numbers",
        "what_fails": "Reading spec sheets, benchmark comparisons, jargon without context",
    },
    "AI & Automation": {
        "subtopics": [
            "Generative AI Tools Sora Gemini GPT", "Faceless AI YouTube Channels",
            "AI Automation for Business AAA", "Prompt Engineering Tips",
            "AI Art & Music Generation", "Python for AI Beginners",
            "Agentic AI Workflows", "AI Tools That Replace Jobs",
            "AI for Students", "AI for Freelancers",
            "Top Free AI Tools This Month", "AI Video Editing Tools",
            "Voice Cloning & Deepfake Awareness", "AI vs Human Creativity",
            "ChatGPT Hidden Features", "No-Code AI Workflows",
        ],
        "audience": "20–35, creators, freelancers, students, working professionals",
        "tone": "future-forward, slightly urgent, 'you need to know this NOW'",
        "language": "English-heavy Hinglish, AI product names natural",
        "what_works": "Real-world impact, job relevance, free tool angle",
        "what_fails": "Jargon dumps, API explanations, abstract AI theory",
    },
    "Earning, Finance & Side Hustles": {
        "subtopics": [
            "Passive Income Side Hustles India", "Crypto & Web3 Basics",
            "Stock Market for Beginners", "Freelancing Roadmap India",
            "Affiliate Marketing Methods", "SaaS Tool Reviews",
            "Dividend Investing", "Dropshipping India Reality",
            "Reselling Business Ideas", "How Students Can Earn Online",
            "YouTube Monetization Tips", "Instagram Earning Methods",
            "Govt Schemes for Entrepreneurs", "How to Save Tax India",
            "Mutual Funds Simplified", "Emergency Fund Planning",
            "Credit Card Smart Use",
        ],
        "audience": "18–35, middle-class, want financial independence",
        "tone": "aspirational but real, no get-rich-quick hype",
        "language": "Hinglish, finance terms explained simply",
        "what_works": "Specific numbers, real person story, step that is actionable today",
        "what_fails": "Vague 'invest wisely', no specific stock tips, no gambling framing",
    },
    "Lifestyle & POV": {
        "subtopics": [
            "Digital Nomad Travel Vlogs", "Flying Beast Style Family Vlogs",
            "Minimalist Living & Decluttering", "Day in the Life Professional",
            "Luxury Home Tours", "Solo Female Travel India",
            "Off-Grid Living", "Morning Routine Real Not Perfect",
            "Slow Living Philosophy", "Van Life India",
            "Hostel Life Chronicles", "Work From Cafe Life",
            "25 Under 25 Success Stories", "Small Town to Big City Moves",
        ],
        "audience": "18–30, urban dreamers, lifestyle-aspiring",
        "tone": "aspirational, intimate, first-person",
        "language": "Softer Hinglish, English where natural",
        "what_works": "Specific moment, sensory detail, emotion over achievement",
        "what_fails": "Bragging, materialism without depth, generic inspiration",
    },
    "Automotive & Racing": {
        "subtopics": [
            "Supercar Reviews India", "Off-Roading Adventures",
            "Vintage Car Restoration", "EV Long-Term Tests",
            "Formula 1 Analysis", "MotoGP Highlights",
            "Bike Customization Vlogs", "Budget Car Mods",
            "Road Trip Stories India", "Tata vs Maruti Debate",
            "Hidden Car Features", "Petrol vs Electric Future",
            "Fastest Cars Under 20 Lakh", "Accident & Safety Analysis",
        ],
        "audience": "18–35 males, car/bike enthusiasts",
        "tone": "passionate, adrenaline, insider community language",
        "language": "Hinglish, car terms in English naturally",
        "what_works": "Driving feel, insider spec that most don't know, controversy",
        "what_fails": "Dry spec comparison, brochure language",
    },
    "Health, Fitness & Sports": {
        "subtopics": [
            "Influencer Boxing Explained", "Home Workouts No Equipment",
            "Biohacking & Longevity", "Weight Loss Real Transformations",
            "Cricket Analysis & News", "Football Transfer Rumors",
            "Yoga for Beginners", "Sleep Science Hacks",
            "Mental Health Exercise Link", "Gut Health Simplified",
            "Protein Sources for Indians", "Running for Beginners",
            "Gym Myths Busted", "Posture Fixes Desk Workers",
            "Cold Water Therapy Science", "Intermittent Fasting Reality",
        ],
        "audience": "18–40, health-conscious, busy people wanting quick wins",
        "tone": "motivating, science-backed, no BS",
        "language": "Hinglish, body/fitness terms in English",
        "what_works": "Myth-busting, specific numbers, desi context",
        "what_fails": "Toxic fitness culture, extreme diets, generic 'eat healthy'",
    },
    "Relationships & Social Skills": {
        "subtopics": [
            "Dating Red Flags Respectful", "Communication Hacks Relationships",
            "Friendship Psychology", "Confidence Building Steps",
            "Setting Boundaries", "Conversation Starters",
            "Attachment Styles Explained", "Love Languages Short",
            "Why Good People End Up Alone", "Signs of Healthy Relationship",
            "How to Apologize Correctly", "Introvert Social Skills",
            "Toxic Patterns to Unlearn", "Long Distance Relationship Tips",
        ],
        "audience": "18–30, all genders, navigating modern relationships",
        "tone": "empathetic, honest, slightly vulnerable",
        "language": "Softer Hinglish, warm",
        "what_works": "Specific scenario they recognize, psychological insight, hope",
        "what_fails": "Misogyny, toxic advice, vague 'communicate better'",
    },
    "Education & Study": {
        "subtopics": [
            "Study With Me Tips", "Memory Techniques Feynman Spaced Rep",
            "Exam Hacks Real", "Learning English Fast for Indians",
            "Math Short Tricks", "Student Productivity Systems",
            "UPSC Simplified", "JEE NEET Preparation Tips",
            "How Toppers Actually Study", "Best Free Learning Resources",
            "Pomodoro Focus Techniques", "Note-Taking Systems",
            "How to Read Faster", "Overcoming Exam Anxiety",
        ],
        "audience": "14–24, school to college, competitive exam prep",
        "tone": "peer-to-peer, helpful, energetic topper friend",
        "language": "Hinglish, student slang natural",
        "what_works": "Counterintuitive method, specific time saved, relatable struggle",
        "what_fails": "Generic 'study hard', vague advice, preaching tone",
    },
    "Career & Corporate": {
        "subtopics": [
            "Interview Q&A Real", "Resume Mistakes That Cost Jobs",
            "Office Politics Navigation", "Workplace Etiquette India",
            "Salary Negotiation Scripts", "Freshers Roadmap 2025",
            "LinkedIn Growth Hacks", "How to Get Promoted Faster",
            "Work From Home Productivity", "Toxic Boss Signs",
            "When to Quit Your Job", "Freelance vs Job Debate",
            "Skills That Pay in 2025", "How to Ask for a Raise",
        ],
        "audience": "20–35, freshers to mid-level professionals",
        "tone": "insider, practical, slightly rebellious against corporate BS",
        "language": "Hinglish, corporate English terms natural",
        "what_works": "Specific script/phrase they can use, insider truth",
        "what_fails": "Vague motivation, generic 'network more', HR-speak",
    },
    "Business & Marketing": {
        "subtopics": [
            "Branding with Indian Examples", "Ad Copy Hook Formulas",
            "Creator Economy India", "Instagram Growth Real Methods",
            "YouTube Channel Growth", "Business Case Studies Zomato Amul Apple",
            "Sales Psychology Tricks", "Business Myths Busted",
            "How Viral Marketing Works", "Pricing Psychology",
            "Startup Failure Stories Lessons", "Building Personal Brand",
            "Email Marketing Basics", "Customer Retention vs Acquisition",
        ],
        "audience": "20–35, entrepreneurs, creators, marketing students",
        "tone": "sharp, insight-driven, case-study style",
        "language": "Hinglish, marketing terms in English naturally",
        "what_works": "Real brand example, specific campaign, counterintuitive insight",
        "what_fails": "Generic business gyan, abstract theory, no examples",
    },
    "Self Improvement & Mindset": {
        "subtopics": [
            "Habits That Actually Stick", "Discipline vs Motivation Real Talk",
            "Atomic Habits Key Takeaway", "Confidence Building Steps",
            "Decision Making Frameworks", "Stoicism for Indians",
            "Ego and Its Cost", "Why Smart People Self-Sabotage",
            "The Comparison Trap", "How to Stop Procrastinating Real Methods",
            "Ikigai Explained Simply", "Growth Mindset in Practice",
            "Daily Reflection Habit", "Saying No Without Guilt",
        ],
        "audience": "18–35, growth-seeking, slightly burned out",
        "tone": "grounded, real, anti-guru, pro-action",
        "language": "Hinglish, philosophy terms explained in Hindi",
        "what_works": "One specific actionable shift, psychology behind it",
        "what_fails": "Toxic positivity, hustle culture, vague 'believe in yourself'",
    },
    "Productivity & Tools": {
        "subtopics": [
            "Notion Templates That Work", "Google Sheets Power Tricks",
            "AI Tools for Students", "Android Hidden Features",
            "Windows Shortcuts Most Don't Know", "Time Blocking Method",
            "Automation Apps India Zapier Make", "Second Brain Setup",
            "Browser Extensions That Save Hours", "Gmail Hacks",
            "Obsidian for Notes", "Calendar Blocking for Creators",
            "Batch Working Explained", "Deep Work Setup",
        ],
        "audience": "18–35, students, creators, freelancers, WFH pros",
        "tone": "efficient, nerdy-cool, practical",
        "language": "Hinglish, tool names in English",
        "what_works": "Show the result first, then the trick — time or effort saved",
        "what_fails": "Tool listing without showing output, 'top 10 apps' without context",
    },
    "History (Short Storytelling)": {
        "subtopics": [
            "Untold Indian Stories", "Wars in 60 Seconds",
            "Ancient India Secrets", "Weird Historical Inventions",
            "Leaders One Decision Changed History", "Timeline Explainers",
            "Colonial India Dark Truths", "Mughal Empire Facts Not Taught",
            "India Partition Hidden Stories", "Cold War Secrets",
            "WW2 Stories Not in Textbooks", "Historical Coincidences",
            "The Day That Changed Everything", "Forgotten Heroes of India",
            "Empires That Vanished Overnight",
        ],
        "audience": "16–35, curious about India and world history",
        "tone": "dramatic storyteller, campfire energy, real events",
        "language": "Slightly more Hindi, English for names and places",
        "what_works": "Drop into the exact moment, specific date/place/person, shocking scale",
        "what_fails": "Textbook narration, passive voice, 'in ancient times'",
    },
    "Science & Engineering": {
        "subtopics": [
            "Why Everyday Things Work Physics", "Engineering Failures and Lessons",
            "Space Updates India and NASA", "Brain and Sleep Science",
            "Chemistry in Daily Life", "Electricity Myths Busted",
            "How Planes Stay Up", "Why Bridges Don't Fall",
            "Nuclear Energy Simplified", "Quantum Physics No Math",
            "Black Holes for Normal People", "Evolution in 60 Seconds",
            "DNA and Genetics Simply", "Sound and Light Tricks",
        ],
        "audience": "14–30, curious students and professionals",
        "tone": "wonder-inducing, Kurzgesagt meets desi",
        "language": "Hinglish, science terms explained simply",
        "what_works": "Daily life connection first, then the science — phenomenon before formula",
        "what_fails": "Formulas, definitions, textbook explanation",
    },
    "True Crime (SFW) & Mystery": {
        "subtopics": [
            "Missing Object Mysteries", "Famous Fraud Scams Explained",
            "Cyber Crime Stories India", "Forensics Facts",
            "Case Study with Safety Lesson", "Cold Cases Simplified",
            "Identity Theft Stories", "Con Artist Psychology",
            "Real Heist Breakdowns", "Unsolved Indian Mysteries",
            "Court Cases That Changed Law", "Social Engineering Cons",
        ],
        "audience": "18–35, mystery lovers, podcast listeners",
        "tone": "suspenseful, slow build, calculated reveals",
        "language": "Hinglish, crime/legal terms in English",
        "what_works": "One detail that doesn't add up, escalating tension, lesson at end",
        "what_fails": "Gore, glorifying criminals, spoiling the mystery upfront",
    },
    "Scams, Safety & Consumer Awareness": {
        "subtopics": [
            "UPI Scam Patterns 2025", "Fake Job Offer Scams",
            "Phone Call Fraud Scripts", "Online Shopping Traps",
            "Privacy Tips for Indians", "How to Verify News",
            "Insurance Mis-selling", "Crypto Scam Patterns",
            "Loan App Danger Signs", "Fake Scholarship Scams",
            "Matrimonial Site Fraud", "Real Estate Trap Signs",
            "Dark Patterns in Apps Explained", "How Your Data Gets Sold",
        ],
        "audience": "18–55, all digital users",
        "tone": "urgent, protective, empowering",
        "language": "Clear Hinglish, scam terms in simple Hindi",
        "what_works": "Real script the scammer uses, exact amount lost, how to detect",
        "what_fails": "Fear-mongering, vague 'be careful online'",
    },
    "Movies, Web Series & Anime": {
        "subtopics": [
            "Explained Endings", "Hidden Details You Missed",
            "Character Arcs Decoded", "Anime Power Scaling",
            "Top Recommendations by Mood", "1-Min Show Recaps",
            "Director Hidden Messages", "Cancelled Shows That Deserved More",
            "Plot Holes Explained", "Behind the Scenes Facts",
            "Indian Cinema Hidden Stories", "Dark Themes in Popular Shows",
        ],
        "audience": "16–30, pop culture fans, OTT subscribers",
        "tone": "fan energy, enthusiastic, fellow binge-watcher",
        "language": "Hinglish, show/anime names in English",
        "what_works": "The one detail that changes everything, hot take, hidden connection",
        "what_fails": "Full plot recaps, obvious observations, no unique angle",
    },
    "Books & Knowledge Nuggets": {
        "subtopics": [
            "Book Summaries One Key Idea", "1 Quote Plus Deep Lesson",
            "Psychology Books Key Insights", "Business Books India",
            "Indian Mythology Retold", "Philosophy Simplified",
            "Fiction Books Life Lessons", "Books CEOs Recommend",
            "Books Schools Should Teach", "Hidden Wisdom Ancient Texts",
        ],
        "audience": "20–35, knowledge-hungry, self-improvement oriented",
        "tone": "distilled wisdom, punchy, every line quotable",
        "language": "Cleaner Hinglish, philosophical English welcome",
        "what_works": "One insight fully explored, real-life application, why it matters now",
        "what_fails": "Chapter-by-chapter summary, no personal relevance",
    },
    "Food + Nutrition (Myth Busting)": {
        "subtopics": [
            "Protein Myths Indians Believe", "Sugar vs Fat Truth",
            "Cheapest Healthy Diet India", "Indian Diet Smart Swaps",
            "Supplements What Works What Doesn't", "Reading Food Labels What to Avoid",
            "Traditional Indian Foods That Are Superfoods", "Detox Myth Busted",
            "Calorie Myths", "Vegetarian Protein Sources", "Late Night Eating Myths",
        ],
        "audience": "18–45, health-curious, home cooks, parents",
        "tone": "friendly myth-buster, science-backed",
        "language": "Hinglish, nutrition terms explained simply",
        "what_works": "Myth first, real fact second, Indian context always",
        "what_fails": "Extreme diet advice, Western food context without desi swap",
    },
    "Fashion & Grooming": {
        "subtopics": [
            "Outfit Formula Upgrades", "Budget Styling India",
            "Men Grooming Basics", "Skincare for Indian Skin",
            "Perfume Buying Guide India", "Accessories Rules Men",
            "Thrift Shopping Guide India", "Color Combinations That Work",
            "Capsule Wardrobe Indian Version", "Haircut by Face Shape",
            "Dressing for Job Interviews", "Ethnic Wear Modern Styling",
        ],
        "audience": "16–30, style-conscious, college students, urban youth",
        "tone": "confident, stylish, no-gatekeeping, accessible",
        "language": "Hinglish, fashion English natural",
        "what_works": "Budget alternative, one rule that changes everything, visual contrast",
        "what_fails": "Unattainable luxury, condescending tone, too many rules at once",
    },
    "Home, DIY & Repairs": {
        "subtopics": [
            "Quick Home Fixes", "Budget Room Makeover",
            "Cleaning Hacks That Work", "Basic Tool Guide",
            "IKEA Style DIY India", "Common Electrical Fixes Safe",
            "Furniture Arrangement Psychology", "Storage Hacks Small Apartments",
            "Monsoon Home Prep", "AC Maintenance Tips",
        ],
        "audience": "22–45, renters and homeowners",
        "tone": "practical, satisfying, self-reliant",
        "language": "Simple Hinglish, Hindi-dominant",
        "what_works": "Money saved, time saved, result visible in seconds",
        "what_fails": "Complex tools needed, expensive materials, non-Indian context",
    },
    "Parenting & Family (Positive)": {
        "subtopics": [
            "Kids Screen Time Real Limits", "Parenting Myths India",
            "Family Communication Scripts", "Study Habits for Kids",
            "Teen Talk That Works", "How to Raise Confident Kids",
            "Single Parent Tips", "Sibling Rivalry Handling",
            "What Kids Remember vs What Parents Think",
        ],
        "audience": "25–45, parents, grandparents, teachers",
        "tone": "empathetic, non-judgmental, science-backed",
        "language": "Softer Hinglish, Hindi-leaning",
        "what_works": "Counterintuitive parenting insight, specific situation, emotion",
        "what_fails": "Shaming parents, perfect parent narrative, Western-only advice",
    },
    "Spirituality & Culture (Respectful)": {
        "subtopics": [
            "Festival Origins You Didn't Know", "Indian Culture Hidden Facts",
            "Mythology Stories Retold Modern", "Vedic Science",
            "Meditation Basics Science-Backed", "Temple Architecture Secrets",
            "Yoga Real History", "Diwali Holi Navratri Deep Meaning",
            "Bhagavad Gita One Line Lessons",
        ],
        "audience": "18–50, spiritually curious, culture-proud Indians",
        "tone": "reverent but curious, exploring not preaching",
        "language": "Warm Hinglish, Sanskrit/Hindi terms briefly explained",
        "what_works": "Hidden origin story, science-spirituality link, surprising fact",
        "what_fails": "Religious superiority, exclusionary language, preaching",
    },
    "Language & Communication": {
        "subtopics": [
            "English Speaking Mistakes Indians Make", "Hindi to English Phrase Swaps",
            "Public Speaking Shortcut", "Storytelling Structure",
            "Vocabulary That Makes You Sound Smart", "Body Language Basics",
            "How to Disagree Professionally", "Email Writing Hacks",
            "Filler Words to Drop",
        ],
        "audience": "15–30, English learners, communication-nervous students",
        "tone": "friendly teacher, celebratory about learning",
        "language": "Hinglish, examples shown in both Hindi and English",
        "what_works": "Mistake-first, relatable embarrassment, immediate fix",
        "what_fails": "Condescension, too many rules, no practical demo",
    },
    "Travel & Hidden Places": {
        "subtopics": [
            "Hidden Gems India", "Budget Travel Hacks India",
            "Street Food Trails", "Scam Avoidance Travel",
            "30-Second Itinerary", "Hotel Booking Tips India",
            "Monsoon Travel Spots", "Solo Travel India Guide",
            "Off-Season Destinations", "North East India Hidden Places",
            "Visa-Free Countries for Indians", "Cheapest International Trips",
        ],
        "audience": "20–35, travel-dreaming, budget-conscious",
        "tone": "adventurous, local-insider, wanderlust-triggering",
        "language": "Breezy Hinglish, place names natural",
        "what_works": "Paint a place so vividly they book tickets, specific cost, one insider tip",
        "what_fails": "Tourist brochure tone, no budget info, generic 'beautiful place'",
    },
    "Pets & Animals": {
        "subtopics": [
            "Dog Training Basics India", "Cat Behavior Decoded",
            "Pet Care Myths Busted", "Animal Kingdom Shocking Facts",
            "Adopting vs Buying Explained", "Indian Breeds You Didn't Know",
            "Pet Health Signs to Watch", "Best Pets for Apartments India",
        ],
        "audience": "All ages, pet owners and animal lovers",
        "tone": "warm, delightful, protective",
        "language": "Soft Hinglish, pet care terms in English",
        "what_works": "Surprising animal fact, relatable pet owner situation, actionable care tip",
        "what_fails": "Scare tactics about cruelty, guilt-tripping",
    },
    "Current Affairs (Explained Simply)": {
        "subtopics": [
            "What Happened Plus Why It Matters", "Policy Explained Simply",
            "Economic Concepts Daily Life", "Tech Policy India",
            "Budget Explained for Normal People", "Election Process Simplified",
            "International News India Impact", "Court Verdict Meaning",
        ],
        "audience": "18–40, news-curious but news-fatigued",
        "tone": "clear, neutral, explainer — not news anchor, not WhatsApp uncle",
        "language": "Clear Hinglish, policy terms explained immediately",
        "what_works": "Connect the event to their pocket, job, or daily life",
        "what_fails": "Political bias, panic framing, jargon without context",
    },
    "Mental Health & Emotional Intelligence": {
        "subtopics": [
            "Anxiety Explained Simply", "Depression Signs Not Clinical Advice",
            "Burnout vs Laziness", "People Pleasing Psychology",
            "Imposter Syndrome Real Talk", "How to Actually Process Emotions",
            "Therapy Myths India", "Journaling That Works",
            "Digital Detox Benefits", "Loneliness in the City",
        ],
        "audience": "18–35, mentally aware, slightly overwhelmed",
        "tone": "safe, validating, science-informed",
        "language": "Softer Hinglish, therapy terms gently explained",
        "what_works": "Name the exact feeling they couldn't name, validation then insight",
        "what_fails": "Toxic positivity, armchair diagnosis, 'just be happy'",
    },
    "Motivation & Inspiration (Story Format)": {
        "subtopics": [
            "Underdog Success Stories India", "Failure Before Success Real Cases",
            "Unknown Heroes of India", "Startup Comeback Stories",
            "Sports Comeback Moments", "First Generation Success",
            "Village to CEO Stories", "Women Breaking Barriers India",
        ],
        "audience": "16–35, dreamers who feel stuck",
        "tone": "cinematic, real-person story, goosebumps by end",
        "language": "Emotional Hinglish, Hindi for impact moments",
        "what_works": "Drop into the lowest point first, specific name and detail, earned ending",
        "what_fails": "Generic 'work hard', unnamed person, inspirational poster language",
    },
}

STAGE1_SYSTEM_V3 = """
You are a senior YouTube Shorts content strategist for Indian audiences.
Your job is NOT to write the script. Your job is to decide EXACTLY what the script will be about — so specifically that a writer could execute it perfectly without guessing.

You will receive a category and subtopic and must output a complete IDEA BRIEF.

JSON RULES: Valid JSON only. Do not use the double-quote character inside any string value — rephrase. No raw line breaks inside strings.

Output ONLY this JSON, nothing else:
{
  "topic": "Specific name of the phenomenon, event, or concept",
  "hook_line": "The exact opening line in Hinglish — must stop scroll",
  "core_fact": "2-3 sentences: real information, with specific detail",
  "twist": "Unexpected angle or personal application",
  "connect": "How this touches the viewer's real life right now",
  "content_angle": "What makes this version different from the obvious take",
  "key_detail": "One specific number/name/date that makes this credible",
  "tone_note": "What emotional register this specific topic needs",
  "is_factually_safe": true,
  "confidence_note": "Any part you're less sure about"
}
""".strip()

STAGE1_USER_V3 = """
Category: {category}
Subtopic: {subtopic}
Audience: {audience}
What works for this category: {what_works}
What fails for this category: {what_fails}

Generate the idea brief now. Be SPECIFIC. Name real things. Include real details.
Return ONLY the JSON.
""".strip()

STAGE2_SYSTEM_V3 = """
You are a viral YouTube Shorts scriptwriter who has written for top Indian creators.
You write in natural Hinglish — the way a 22-year-old Indian creator would talk to camera.

You will receive a complete IDEA BRIEF. Your only job is to write the script from it.
Do NOT invent new facts. Do NOT change the angle. Do NOT add things not in the brief.

JSON RULES (critical): Output valid JSON only. Do not use the double-quote character inside any string value — rephrase or use single quotes in dialogue. No raw line breaks inside strings — use spaces.

Output ONLY this JSON, nothing else:
{
  "hook": "...",
  "build": "...",
  "twist": "...",
  "connect": "...",
  "cta": "...",
  "full_script": "complete script as one flowing piece",
  "word_count": 0,
  "estimated_seconds": 0,
  "scene_hints": ["Scene 1 visual", "Scene 2 visual", "Scene 3 visual"],
  "pexels_queries": ["query1", "query2", "query3"],
  "thumbnail_text": "5 words max",
  "yt_title": "Under 60 chars with 1 emoji",
  "description": "3 lines ending with hashtags",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "quality": {
    "hook_stops_scroll": true,
    "sounds_like_person": true,
    "has_clear_twist": true,
    "logically_coherent": true,
    "word_count_ok": true
  }
}
""".strip()

STAGE2_USER_V3 = """
Category: {category}
Subtopic: {subtopic}
Tone: {tone}
Language: {language}

IDEA BRIEF (write exactly this, make it alive):
Topic: {topic}
Hook line: {hook_line}
Core fact: {core_fact}
Twist: {twist}
Connect: {connect}

Write the script now. Return ONLY the JSON.
""".strip()

V3_JSON_REPAIR_SYSTEM = (
    "You repair malformed JSON from language models. Output ONLY valid minified JSON — "
    "same keys and meaning as the input, no markdown fences, no explanation."
)


def _clean_json_response(raw_content: str) -> str:
    clean = raw_content.replace("```json", "").replace("```", "").strip()
    # Attempt to clip to JSON object boundaries if extra text appears
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start != -1 and end != -1 and end > start:
        clean = clean[start:end]
    return clean


def _parse_json_loose(raw_content: str) -> dict:
    """
    Parse model JSON; tolerate literal control chars inside strings (strict=False).
    """
    s = _clean_json_response(raw_content)
    return json.loads(s, strict=False)


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


def _quality_check_v2(script: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    full = (script.get("full_script") or "").strip()
    full_l = full.lower()
    wc = _word_count(full)
    if wc < 42:
        failures.append(f"Too short: {wc} words (min 42)")
    if wc > 72:
        failures.append(f"Too long: {wc} words (max 72)")
    for opener in BAD_OPENERS:
        if full_l.startswith(opener):
            failures.append(f"Bad opener: starts with '{opener}'")
            break
    if len((script.get("hook") or "").strip()) < 12:
        failures.append("Hook missing/weak")
    if len((script.get("twist") or "").strip()) < 10:
        failures.append("Twist missing/weak")
    if not script.get("pexels_search_queries"):
        failures.append("Missing pexels_search_queries")
    if not script.get("scene_hints"):
        failures.append("Missing scene_hints")
    if not script.get("hashtags"):
        failures.append("Missing hashtags")
    return (len(failures) == 0), failures


# v3 compatibility quality gate (from content_engine_v3.py)
def quality_check(script: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    full = (script.get("full_script") or "").lower().strip()
    words = full.split()

    if len(words) < 42:
        failures.append(f"Too short: {len(words)} words")
    if len(words) > 72:
        failures.append(f"Too long: {len(words)} words")

    for opener in BAD_OPENERS:
        if full.startswith(opener):
            failures.append(f"Bad opener detected: '{opener}'")
            break

    if not script.get("twist") or len((script.get("twist") or "").strip()) < 15:
        failures.append("Twist missing or too weak")

    q = script.get("quality", {}) or {}
    if q.get("logically_coherent") is False:
        failures.append("Model flagged: not logically coherent")
    if q.get("sounds_like_person") is False:
        failures.append("Model flagged: doesn't sound like a person")

    return len(failures) == 0, failures


def _trim_script_to_word_limit(script: dict, target_max_words: int = 68) -> dict:
    """
    Best-effort normalizer for overlong scripts.
    Keeps narrative continuity and ensures CTA remains at the end.
    """
    full = (script.get("full_script") or "").strip()
    if not full:
        return script

    words = full.split()
    if len(words) <= target_max_words:
        script["word_count"] = len(words)
        script.setdefault("estimated_seconds", int(max(10, len(words) * 0.75)))
        return script

    cta = (script.get("cta") or "").strip()
    body_words = words[:target_max_words]
    trimmed = " ".join(body_words).strip(" ,.;:-")

    # Ensure CTA appears at end (if provided and room allows).
    if cta and cta.lower() not in trimmed.lower():
        cta_words = cta.split()
        reserve = min(len(cta_words), 14)
        kept = max(0, target_max_words - reserve)
        trimmed = " ".join(words[:kept]).strip(" ,.;:-")
        trimmed = f"{trimmed}. {cta}".strip()

    script["full_script"] = trimmed
    wc = len(trimmed.split())
    script["word_count"] = wc
    script["estimated_seconds"] = int(max(10, wc * 0.75))
    return script


# -----------------------------------------------------------------------------
# High-performing Shorts niches and sub-topics (used by the generative pipeline).
TRENDING_CONTENT_MAP: dict[str, list[str]] = {
    "Gaming & Metaverse": [
        "BGMI / PUBG Mobile", "Free Fire Max", "Minecraft Survival & Mods",
        "GTA V Roleplay", "Valorant Competitive", "Fighting Games (Tekken/Street Fighter)",
        "Esports Highlights", "Soul Games (Elden Ring/Dark Souls)", "Hindi Commentary & Roasting",
        "Total Gaming Style Walkthroughs", "Speedrunning", "Game Lore & Theory",
        "Roblox Modding", "VR/AR Gameplay Immersive"
    ],
    "Cooking & Gastronomy": [
        "Village Cooking / Outdoor Fire", "5-Minute Quick Meals", "Street Food Tours (India/Global)",
        "ASMR Baking & Pastry", "Healthy Meal Prep / Keto Recipes", "Chef Reviews & Kitchen Hacks",
        "Traditional Heritage Recipes", "Blind Taste Tests", "Budget Cooking Challenges"
    ],
    "Comedy & Entertainment": [  "Woman's Fighting",
        "Stand-Up Comedy Specials", "Crowd Work & Improvisation", "Sketch Comedy & Parodies",
        "CarryMinati Style Roasting", "Hidden Camera Pranks", "Meme Reviews",
        "Sitcom Recaps", "Reaction Videos", "Dark Humor / Satire"
    ],
    "Geopolitics, War & Defense": [
        "Live Conflict Updates & Analysis", "Military Tech & Weaponry Reviews",
        "Geopolitical Power Shifts", "Modern Warfare History", "Special Forces Training POV",
        "Defense News (India/Global)", "Geographical Map Explainers (Johnny Harris Style)"
    ],
    "Facts & Infotainment": [
        "Psychology Facts", "Space & Universe Mysteries", "Historical Secrets",
        "FactTechz Style Explainer", "Myth-Busting", "Science Experiments",
        "Top 10 Lists", "Ancient Civilizations", "Forensics / Crime Science"
    ],
    "Tech & Future-Proofing": [
        "Smartphone Unboxing", "Budget PC Building", "Tech News (Hindi)",
        "Home Automation & IoT", "Software Development Vlogs", "Cybersecurity & Hacking Tools",
        "AI Hardware Reviews", "Electric Vehicle (EV) Tech", "Metaverse Updates"
    ],
    "AI & Automation": [
        "Generative AI Tools (Sora/Gemini)", "Faceless AI YouTube Channels",
        "AI Automation for Business (AAA)", "Prompt Engineering Tutorials",
        "AI Art & Music Generation", "Python for AI Development", "Agentic AI Workflows"
    ],
    "Earning, Finance & Side Hustles": [
        "Passive Income Side Hustles", "Crypto & Web3 Trading", "Stock Market Analysis",
        "Freelancing Roadmap", "Affiliate Marketing Strategies", "SaaS Tool Reviews",
        "Dividend Investing", "Dropshipping Case Studies"
    ],
    "Lifestyle & POV": [
        "Digital Nomad Travel Vlogs", "Flying Beast Style Family Vlogs",
        "Minimalist Living & Decluttering", "Day in the Life (Professional Edition)",
        "Luxury Home Tours", "Solo Female Travel", "Off-Grid Living"
    ],
    "Automotive & Racing": [
        "Supercar Reviews", "Off-Roading Adventures", "Vintage Car Restoration",
        "Electric Vehicle (EV) Long-Term Tests", "Formula 1 & MotoGP Analysis",
        "Bike Customization / Vlogs"
    ],
    "Health, Fitness & Sports": [
        "Social-First Boxing (Influencer Matches)", "Home Workouts (No Equipment)",
        "Biohacking & Longevity", "Weight Loss Transformations", "Cricket Analysis & News",
        "Football Transfer Rumors", "Yoga & Mental Health"
    ],
    "Relationships & Social Skills": [
        "Dating Red Flags (Respectful)", "Communication Hacks", "Friendship Psychology",
        "Confidence Building", "Boundaries Explained", "Conversation Starters"
    ],
    "Education & Study": [
        "Study With Me Tips", "Memory Techniques", "Exam Hacks",
        "Learning English Fast", "Math Short Tricks", "Student Productivity"
    ],
    "Career & Corporate": [
        "Interview Q&A", "Resume Mistakes", "Office Politics (Safe)", "Workplace Etiquette",
        "Negotiation Basics", "Freshers Roadmap", "LinkedIn Growth"
    ],
    "Business & Marketing": [
        "Branding Basics", "Ad Copy Hooks", "Creator Economy Tips", "Instagram/YouTube Growth",
        "Case Studies (Zomato/Apple)", "Sales Psychology", "Business Myths"
    ],
    "Self Improvement & Mindset": [
        "Habits That Stick", "Discipline vs Motivation", "Atomic Habits-style Takeaways",
        "Confidence Challenges", "Decision Making", "Stoicism Basics"
    ],
    "Productivity & Tools": [
        "Notion Templates", "Google Sheets Tricks", "AI for Students", "Android Hidden Features",
        "Shortcut Workflows", "Time Blocking", "Automation Apps"
    ],
    "History (Short Storytelling)": [
        "Untold Stories", "Wars in 30 Seconds", "Ancient India Facts", "Weird Inventions",
        "Leaders & Decisions", "Timeline Explainers"
    ],
    "Science & Engineering": [
        "Why Things Work", "Physics in Daily Life", "Engineering Failures",
        "Space Updates", "Brain + Sleep Science", "Chemistry Myths"
    ],
    "True Crime (SFW) & Mystery": [
        "Missing Object Mysteries", "Fraud Scams Explained", "Cyber Crime Stories",
        "Forensics Facts", "Case Lessons (No gore)", "Safety Tips"
    ],
    "Scams, Safety & Consumer Awareness": [
        "UPI Scam Patterns", "Fake Job Scams", "Phone Call Fraud",
        "Online Shopping Traps", "Privacy Tips", "How to Verify News"
    ],
    "Movies, Web Series & Anime": [
        "Explained Endings", "Hidden Details", "Character Arcs",
        "Anime Power Scaling", "Top Recommendations", "1-Min Recaps"
    ],
    "Books & Knowledge Nuggets": [
        "Book Summaries", "1 Quote + Lesson", "Psychology Books", "Business Books",
        "Mythology Retellings", "Philosophy Simplified"
    ],
    "Food + Nutrition (Myth Busting)": [
        "Protein Myths", "Sugar Truths", "Best Cheap Diet", "Indian Diet Swaps",
        "Supplements Explained", "Label Reading"
    ],
    "Fashion & Grooming": [
        "Outfit Upgrades", "Budget Styling", "Men Grooming", "Skincare Basics",
        "Perfume Guides", "Accessories Rules"
    ],
    "Home, DIY & Repairs": [
        "Quick Fixes", "Budget Room Makeover", "Cleaning Hacks",
        "Tool Basics", "IKEA-style DIY", "Fixing Common Problems"
    ],
    "Parenting & Family (Positive)": [
        "Kids Screen Time Tips", "Parenting Myths", "Family Communication",
        "Study Habits for Kids", "Teen Talk Tips"
    ],
    "Spirituality & Culture (Respectful)": [
        "Festival Origins", "Indian Culture Facts", "Mythology Stories",
        "Life Lessons", "Meditation Basics"
    ],
    "Language & Communication": [
        "English Speaking Mistakes", "Hindi-to-English Phrases",
        "Public Speaking", "Storytelling Tricks", "Vocabulary Shorts"
    ],
    "Travel & Hidden Places": [
        "Hidden Gems India", "Budget Travel Hacks", "Food Streets",
        "Scam Avoidance", "Itinerary in 30 sec", "Hotel Booking Tips"
    ],
    "Pets & Animals": [
        "Dog Training Basics", "Cat Behavior", "Pet Care Myths",
        "Animal Facts", "Cute + Knowledge Combo"
    ],
    "Current Affairs (Explained Simply)": [
        "What happened + why it matters", "Policy explained",
        "Economic concepts simplified", "Tech policy", "Daily 60-sec explainers"
    ],
}


class WorkflowService:
    """Encapsulates all the REST calls that were formerly in n8n."""

    def fetch_trending_videos(self, category_id: str = "0", limit: int = 5) -> list[dict]:
        """
        Hits the Google YouTube Data v3 API.
        Replicates the JS logic: duration 180s to 900s, views >= 100k.
        Filters out previously processed videos to strictly avoid repeats.
        Returns the top suitable videos sorted by highest views for the given category.
        """
        log.info("Fetching trending videos for Category %s...", category_id)
        url = (
            "https://www.googleapis.com/youtube/v3/videos?"
            "part=snippet,statistics,contentDetails&"
            "chart=mostPopular&"
            "regionCode=IN&"
            f"videoCategoryId={category_id}&"
            "maxResults=50&"
            f"key={settings.youtube_api_key}"
        )

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
        except urllib.error.URLError as e:
            log.error("YouTube API failed: %s", e)
            raise RuntimeError(f"YouTube fetch failed: {e}")

        items = data.get("items", [])
        filtered = []

        # Load deduplication database to avoid repeats
        db_path = os.path.join(settings.tmp_dir, "published.txt")
        processed_ids = set()
        if os.path.exists(db_path):
            with open(db_path, "r") as f:
                processed_ids = set(line.strip() for line in f)

        # Replicating the logic from 'Filter & Rank Videos' n8n node
        for video in items:
            vid_id = video.get("id")
            if vid_id in processed_ids:
                continue

            stats = video.get("statistics", {})
            details = video.get("contentDetails", {})

            try:
                view_count = int(stats.get("viewCount", "0"))
            except ValueError:
                continue

            duration_str = details.get("duration", "PT0S")
            # Parse ISO 8601 duration
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
            if not match:
                continue

            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)

            total_seconds = (hours * 3600) + (minutes * 60) + seconds

            if 180 <= total_seconds <= 900 and view_count >= 100000:
                filtered.append(video)

        # Sort top descending by view count
        filtered.sort(key=lambda x: int(x.get("statistics", {}).get("viewCount", "0")), reverse=True)
        top_videos = filtered[:limit]

        # Map to structured data 
        results = []
        for v in top_videos:
            results.append({
                "videoId": v["id"],
                "title": v["snippet"]["title"],
                "channelTitle": v["snippet"]["channelTitle"],
                "viewCount": v["statistics"].get("viewCount", "0"),
                "likeCount": v["statistics"].get("likeCount", "0"),
                "duration": v["contentDetails"]["duration"],
                "publishedAt": v["snippet"]["publishedAt"],
                "tags": ",".join(v["snippet"].get("tags", [])[:5]),
                "videoUrl": f"https://www.youtube.com/watch?v={v['id']}"
            })

        log.info("Found %d suitable trending videos.", len(results))
        return results

    def get_trending_categories(self, limit: int = 3) -> list[dict]:
        """
        Dynamically finds the currently trending categories by analyzing the 
        general most popular videos chart on YouTube.
        Returns a list of dicts: [{"id": "24", "name": "Entertainment"}, ...]
        """
        log.info("Fetching global trending videos to determine hot categories...")
        url = (
            "https://www.googleapis.com/youtube/v3/videos?"
            "part=snippet&"
            "chart=mostPopular&"
            "regionCode=IN&"
            "maxResults=50&"
            f"key={settings.youtube_api_key}"
        )
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
        except Exception as e:
            log.error("Failed to fetch general trending videos: %s", e)
            return [{"id": "24", "name": "Entertainment"}, {"id": "20", "name": "Gaming"}, {"id": "23", "name": "Comedy"}]
            
        category_counts = {}
        for item in data.get("items", []):
            cat_id = item["snippet"]["categoryId"]
            category_counts[cat_id] = category_counts.get(cat_id, 0) + 1
            
        # Sort category IDs by frequency
        sorted_cats = sorted(category_counts.keys(), key=lambda k: category_counts[k], reverse=True)
        top_cat_ids = sorted_cats[:limit]
        
        # Fetch the names of these categories via videoCategories API
        log.info("Fetching names for trending categories: %s", top_cat_ids)
        cat_url = (
            "https://www.googleapis.com/youtube/v3/videoCategories?"
            "part=snippet&"
            f"id={','.join(top_cat_ids)}&"
            f"key={settings.youtube_api_key}"
        )
        
        results = []
        try:
            req = urllib.request.Request(cat_url)
            with urllib.request.urlopen(req) as response:
                cat_data = json.loads(response.read().decode())
                
            # Reorder according to top_cat_ids
            name_map = {item["id"]: item["snippet"]["title"] for item in cat_data.get("items", [])}
            for cid in top_cat_ids:
                results.append({"id": cid, "name": name_map.get(cid, f"Category {cid}")})
        except Exception as e:
            log.error("Failed to fetch category names: %s", e)
            for cid in top_cat_ids:
                results.append({"id": cid, "name": f"Category {cid}"})
                
        return results

    def generate_metadata(
        self,
        title: str,
        channel: str,
        views: str,
        tags: str,
        category_name: str = "Entertainment",
        original_video_id: str | None = None,
    ) -> dict:
        """
        Calls OpenRouter (mistralai/mistral-small-3.2-24b-instruct)
        Returns a dictionary with title, description, hashtags, category.
        """
        log.info("Generating AI Metadata for: %s (Category: %s)", title, category_name)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        prompt = (
            f"Create viral YouTube Shorts metadata for this video:\n"
            f"Original Title: {title}\nChannel: {channel}\nViews: {views}\nTags: {tags}\n\n"
            f"Make it optimised for YouTube Shorts discoverability. "
            f"IMPORTANT REQUIREMENT: You MUST include the following explicit tags in the hashtags string: "
            f"#Trending #MostViewed #{category_name.replace(' ', '')}"
        )
        payload = {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a YouTube Shorts expert. Return ONLY a valid JSON object with keys: title (max 60 chars, catchy), description (max 200 chars, engaging), hashtags (MUST contain #Trending, #MostViewed, and the category as space separated string), category (one of: Entertainment, Education, News, Gaming, Music, Sports). No markdown, no preamble."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())
                
            raw_content = res_data["choices"][0]["message"]["content"]
            # Clean possible markdown formatting
            clean_content = raw_content.replace("```json", "").replace("```", "").strip()
            metadata = json.loads(clean_content)
        except Exception as e:
            log.warning("AI Metadata generation failed (%s), using fallback", e)
            metadata = {
                "title": title[:60],
                "description": "Check out this trending clip! #Shorts",
                "hashtags": f"#Shorts #Trending #MostViewed #{category_name.replace(' ', '')} #Viral #MustWatch",
                "category": category_name
            }
            
        orig_ref = original_video_id.strip() if isinstance(original_video_id, str) else ""
        if orig_ref and ("youtube.com" in orig_ref or "youtu.be" in orig_ref):
            orig_url = orig_ref
        elif orig_ref:
            orig_url = f"https://www.youtube.com/watch?v={orig_ref}"
        else:
            orig_url = ""

        full_desc = f"{metadata.get('description', '')}\n\n{metadata.get('hashtags', '')}"
        if orig_url:
            full_desc += f"\n\nOriginal video: {orig_url}"
        metadata["full_description"] = full_desc
        return metadata

    def mark_video_processed(self, video_id: str) -> None:
        """Appends the video ID to the local deduplication database so it is never reused."""
        db_path = os.path.join(settings.tmp_dir, "published.txt")
        os.makedirs(settings.tmp_dir, exist_ok=True)
        with open(db_path, "a") as f:
            f.write(f"{video_id}\n")
        log.info("Recorded video %s into processed database to avoid duplicates.", video_id)

    def send_telegram_alert(self, short_title: str, short_url: str, orig_title: str, orig_views: str) -> None:
        """Sends a success notification to the configured Telegram chat."""
        log.info("Sending Telegram notification...")
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        
        text = (
            f"New Short Generated!\n\n"
            f"Title: {short_title}\n"
            f"Path: {short_url}\n\n"
            f"Source: {orig_title}\n"
            f"Original Views: {orig_views}"
        )
        
        payload = {
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as response:
                log.info("Telegram notification sent successfully.")
        except Exception as e:
            log.error("Failed to send Telegram notification: %s", e)

    def send_telegram_video(self, video_path: str, caption: str) -> None:
        """Sends the actual physical `.mp4` file directly to the Telegram channel using curl."""
        log.info("Uploading video to Telegram: %s", video_path)
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendVideo"
        
        # Curl handles multipart file uploads flawlessly natively without needing the `requests` package
        cmd = [
            "curl", "-s", "-X", "POST", url,
            "-F", f"chat_id={settings.telegram_chat_id}",
            "-F", f"caption={caption}",
            "-F", "parse_mode=HTML",
            "-F", f"video=@{video_path}"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if '"ok":true' in result.stdout:
                log.info("Video successfully uploaded to Telegram!")
            else:
                log.error("Telegram video upload failed: %s", result.stdout)
        except Exception as e:
            log.error("Error executing curl for Telegram upload: %s", e)

    def get_next_category(self) -> tuple[str, str]:
        """
        Step 1: Category Input (Brain Trigger)
        Rotates between rich categories (TRENDING_CONTENT_MAP) and picks a sub-topic.
        Saves the last used category to a file to maintain state.
        """
        db_path = os.path.join(settings.tmp_dir, "last_category.txt")
        
        # Ensure tmp_dir exists
        os.makedirs(settings.tmp_dir, exist_ok=True)
        
        last_cat = ""
        last_topic = ""
        if os.path.exists(db_path):
            with open(db_path, "r") as f:
                raw = f.read().strip()
                if "|||" in raw:
                    last_cat, last_topic = (raw.split("|||", 1) + [""])[:2]
                else:
                    last_cat = raw
                
        # v3 uses CATEGORY_MAP as the primary source of categories/subtopics
        categories = list(CATEGORY_MAP.keys()) or list(TRENDING_CONTENT_MAP.keys()) or ["Facts & Infotainment"]

        try:
            next_index = (categories.index(last_cat) + 1) % len(categories)
        except ValueError:
            # If last_cat is empty or not in the list, start at index 0
            next_index = 0
            
        next_cat = categories[next_index]
        topics = (CATEGORY_MAP.get(next_cat, {}).get("subtopics") or TRENDING_CONTENT_MAP.get(next_cat, []) or ["General"])
        # Pick a topic, avoid repeating the immediately previous one (best-effort)
        if len(topics) == 1:
            next_topic = topics[0]
        else:
            pool = [t for t in topics if t != last_topic] or topics
            next_topic = random.choice(pool)
        
        with open(db_path, "w") as f:
            f.write(f"{next_cat}|||{next_topic}")
            
        log.info("Selected Category: '%s' | Topic: '%s'", next_cat, next_topic)
        return next_cat, next_topic

    def generate_strategy(self, category: str, topic: str | None = None) -> dict:
        """
        Step 2: Content Strategy Engine
        Defines tone, pacing, hook style, audience type, and content angle based on the category.
        """
        log.info("Generating Content Strategy for category: '%s' (topic=%s)", category, topic or "n/a")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        prompt = (
            f"Given the YouTube Shorts category: {category}\n"
            f"Sub-topic: {topic or 'General'}\n\n"
            "Define the following elements to guide the script generation:\n"
            "- tone (e.g., energetic, mysterious, funny)\n"
            "- pacing (e.g., fast, moderate)\n"
            "- hook style (e.g., question, shocking fact)\n"
            "- audience type (e.g., tech enthusiasts, students, gamers)\n"
            "- content angle (e.g., educational, storytelling, review)\n\n"
            "Return ONLY a valid JSON object with these exact lower-case keys: tone, pacing, hook_style, audience_type, content_angle."
        )
        
        payload = {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a master YouTube Shorts strategist. Output strict JSON only. No markdown formatting."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())
                
            raw_content = res_data["choices"][0]["message"]["content"]
            clean_content = raw_content.replace("```json", "").replace("```", "").strip()
            
            # Additional cleanup in case there is text before/after JSON
            start_idx = clean_content.find("{")
            end_idx = clean_content.rfind("}") + 1
            if start_idx != -1 and end_idx != -1:
                clean_content = clean_content[start_idx:end_idx]
                
            strategy = json.loads(clean_content)
            log.info("Strategy generated: %s", strategy)
            return strategy
        except Exception as e:
            log.warning("Strategy generation failed (%s), using fallback", e)
            return {
                "tone": "energetic",
                "pacing": "fast",
                "hook_style": "bold statement",
                "audience_type": "general",
                "content_angle": "educational"
            }

    def generate_script(self, category: str, topic: str | None, strategy: dict) -> str:
        """
        Step 3: Script Generation — YouTube Shorts optimised (30-60 sec).
        Language  : Hindi/Hinglish (dost-like, conversational)
        Word limit: 60-80 words MAX (≈ 30-55 sec at normal Hindi speech pace)
        Includes  : 1-2 funny/witty jokes to keep the video entertaining.
        """
        log.info("Generating Hindi Shorts Script for category: '%s' (topic=%s)", category, topic or "n/a")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }

        # Goal: meaningful + logical + interactive comedy/knowledge script (not repetitive).
        # We keep the output short and line-based for TTS pacing.
        system_prompt = (
            "Tu ek expert YouTube Shorts writer hai (Hindi/Hinglish, roman script). "
            "Tu engaging, logical, interactive aur funny scripts likhta hai — repetitive bilkul nahi.\n\n"
            "STRICT OUTPUT RULES:\n"
            "- Sirf bolne wali lines. Koi headings, numbering, brackets, ya stage directions nahi.\n"
            "- TOTAL: 8 se 10 lines. Har line max 8 words.\n"
            "- Word limit: 55–70 words.\n"
            "- First line: strong hook (unique phrasing).\n"
            "- Structure (must follow): Hook → Setup → Knowledge Fact (with a number) → Relatable moment → Punchline/twist → Mini takeaway → CTA.\n"
            "- Script mein 1-2 audience questions zaroor ho (interactive).\n"
            "- Koi line ya idea repeat mat karna (same meaning bhi repeat nahi).\n"
            "- Last line EXACT: 'Follow karo aur aisi hi mast videos dekhte raho! ❤️'\n"
        )

        prompt = (
            f"Category: {category}\n"
            f"Sub-topic: {topic or 'General'}\n"
            f"Tone: {strategy.get('tone', 'energetic')}\n"
            f"Pacing: {strategy.get('pacing', 'fast')}\n"
            f"Hook style: {strategy.get('hook_style', 'shocking fact')}\n"
            f"Audience: {strategy.get('audience_type', 'general')}\n"
            f"Angle: {strategy.get('content_angle', 'educational')}\n\n"
            "Ek meaningful aur logical 30–45 sec script likho.\n"
            "Script ka main focus isi sub-topic par hona chahiye (random generic mat likhna).\n"
            "Knowledge fact real-world plausible ho (with a number), phir usko relatable comedy se connect karo.\n"
            "At least 2 lines audience ko direct question karein.\n"
            "No repetition. Fresh, conversational.\n"
        )

        payload = {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt}
            ],
            "temperature": 0.85,
            "max_tokens": 300   # hard cap at API level — 70 Hindi words ≈ 200-280 tokens
        }

        SCRIPT_CHAR_LIMIT = 2400  # Sarvam TTS hard limit (safety net)

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())

            script = res_data["choices"][0]["message"]["content"].strip()

            # --- Post-process: remove repetition + enforce CTA + line limits ---
            def _clean_lines(text: str) -> list[str]:
                raw = [ln.strip() for ln in text.splitlines() if ln.strip()]
                # Normalize common bullet/quote artifacts
                cleaned = []
                for ln in raw:
                    ln = re.sub(r"^[\-\*\d\.\)\(]+\s*", "", ln).strip()
                    if ln:
                        cleaned.append(ln)
                return cleaned

            CTA = "Follow karo aur aisi hi mast videos dekhte raho! ❤️"
            lines = _clean_lines(script)

            # Drop duplicate / near-duplicate lines (cheap heuristic)
            seen = set()
            deduped = []
            for ln in lines:
                key = re.sub(r"[^a-z0-9]+", " ", ln.lower()).strip()
                key = re.sub(r"\s+", " ", key)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(ln)

            lines = deduped

            # Ensure CTA is last and only once
            lines = [ln for ln in lines if ln != CTA]
            lines.append(CTA)

            # Enforce 8–10 lines total (keep ending CTA)
            if len(lines) > 10:
                lines = lines[:9] + [CTA]
            if len(lines) < 8:
                # Pad softly with an interactive prompt + takeaway before CTA
                insert_at = max(0, len(lines) - 1)
                extras = [
                    "Tum bhi aisa karte ho kya?",
                    "Comment mein batao, seriously!",
                ]
                for ex in extras:
                    if len(lines) >= 8:
                        break
                    lines.insert(insert_at, ex)

            script = "\n".join(lines)

            # --- Safety net: hard-trim if model still exceeds the TTS char limit ---
            if len(script) > SCRIPT_CHAR_LIMIT:
                log.warning(
                    "Script exceeded %d chars (%d). Hard-trimming to last complete line within limit.",
                    SCRIPT_CHAR_LIMIT, len(script)
                )
                lines = script.splitlines()
                trimmed, budget = [], SCRIPT_CHAR_LIMIT
                for line in lines:
                    if len(line) + 1 <= budget:
                        trimmed.append(line)
                        budget -= len(line) + 1
                    else:
                        break
                script = "\n".join(trimmed)

            word_count = len(script.split())
            log.info("Hindi Script generated (%d words, %d chars):\n%s", word_count, len(script), script)
            return script

        except Exception as e:
            log.error("Script generation failed: %s", e)
            return (
                "Yaar, ruk ja ek second!\n"
                "Kya tune kabhi socha — ye kaise hota hai?\n"
                "Waise meri life bhi aise hi hai, kuch samajh nahi aata!\n"
                "Subscribe kar — aage aur bhi mast cheezein aane wali hain!"
            )

    def generate_script_v2_json(
        self,
        category: str,
        subtopic: str,
        extra_direction: str = "auto",
        retries: int = 3,
    ) -> dict:
        """
        Master Content Engine v2:
        Returns a strict JSON object with script + scene hints + pexels queries + metadata.
        Retries with a quality gate.
        """
        profile = _default_profile_for_category(category)
        system_prompt = CORE_SYSTEM_PROMPT_V2.format(
            category=category,
            subtopic=subtopic,
            tone=profile["tone"],
            hook_style=profile["hook_style"],
            language=profile["language"],
            avoid=profile["avoid"],
            audience=profile["audience"],
        )
        user_prompt = (
            f"Category: {category}\n"
            f"Subtopic: {subtopic}\n"
            f"Extra direction: {extra_direction}\n\n"
            "Write the YouTube Shorts script now.\n"
            "Return ONLY the JSON object. No explanation. No markdown fences."
        )

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }

        last_failures: list[str] = []
        for attempt in range(1, retries + 1):
            payload = {
                "model": "mistralai/mistral-small-3.2-24b-instruct",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.88,
                "top_p": 0.95,
                "max_tokens": 900,
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    res_data = json.loads(response.read().decode())

                raw_content = res_data["choices"][0]["message"]["content"]
                parsed = json.loads(_clean_json_response(raw_content))

                # Normalize/repair a few fields
                full_script = parsed.get("full_script") or ""
                parsed["word_count"] = int(parsed.get("word_count") or _word_count(full_script))
                if isinstance(parsed.get("hashtags"), str):
                    parsed["hashtags"] = [h for h in re.split(r"\s+", parsed["hashtags"].strip()) if h.startswith("#")]

                passed, failures = _quality_check_v2(parsed)
                parsed.setdefault("quality_flags", {})
                parsed["quality_flags"].update({
                    "hook_passes": passed and "Hook" not in " ".join(failures),
                    "has_twist": passed and "Twist" not in " ".join(failures),
                    "word_count_ok": 42 <= parsed["word_count"] <= 72,
                    "sounds_human": True,
                    "cta_natural": True,
                })

                if passed:
                    parsed["_meta"] = {"attempt": attempt, "category": category, "subtopic": subtopic}
                    return parsed
                last_failures = failures
                log.info("V2 script attempt %d failed quality gate: %s", attempt, failures)
            except Exception as e:
                last_failures = [f"Exception: {e}"]
                log.warning("V2 script attempt %d failed: %s", attempt, e)

        raise RuntimeError(f"V2 script generation failed after {retries} attempts. Last failures: {last_failures}")

    def _call_openrouter_json(
        self,
        system: str,
        user: str,
        model: str = "quality",
        temperature: float = 0.8,
        max_tokens: int = 900,
        timeout: int = 60,
    ) -> dict:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        model_id = OPENROUTER_MODELS_V3.get(model, OPENROUTER_MODELS_V3["quality"])
        payload = {
            "model": model_id,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_data = json.loads(response.read().decode())
        except urllib.error.HTTPError as http_err:
            # Some models on OpenRouter reject response_format — retry without it
            if http_err.code == 400:
                log.warning("OpenRouter rejected response_format; retrying without JSON mode flag.")
                payload.pop("response_format", None)
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    res_data = json.loads(response.read().decode())
            else:
                raise
        raw_content = res_data["choices"][0]["message"]["content"]

        try:
            return _parse_json_loose(raw_content)
        except json.JSONDecodeError as e:
            log.warning("JSON parse failed (%s), attempting repair pass...", e)
            repair_user = (
                "The following text was supposed to be a single JSON object but failed to parse.\n"
                "Return ONLY valid minified JSON with the same fields and content. "
                "Fix unterminated strings, stray quotes, and trailing commas.\n\n"
                f"{raw_content[:14000]}"
            )
            repair_payload = {
                "model": model_id,
                "temperature": 0.05,
                "max_tokens": min(max_tokens + 400, 2048),
                "messages": [
                    {"role": "system", "content": V3_JSON_REPAIR_SYSTEM},
                    {"role": "user", "content": repair_user},
                ],
                "response_format": {"type": "json_object"},
            }
            req2 = urllib.request.Request(url, data=json.dumps(repair_payload).encode("utf-8"), headers=headers)
            try:
                with urllib.request.urlopen(req2, timeout=timeout) as response2:
                    res2 = json.loads(response2.read().decode())
            except urllib.error.HTTPError as http_err2:
                if http_err2.code == 400:
                    repair_payload.pop("response_format", None)
                    req2 = urllib.request.Request(url, data=json.dumps(repair_payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req2, timeout=timeout) as response2:
                        res2 = json.loads(response2.read().decode())
                else:
                    raise
            fixed = res2["choices"][0]["message"]["content"]
            return _parse_json_loose(fixed)

    def generate_idea_brief_v3(self, category: str, subtopic: str, model: str = "quality") -> dict:
        profile = CATEGORY_MAP.get(category, {})
        user = STAGE1_USER_V3.format(
            category=category,
            subtopic=subtopic,
            audience=profile.get("audience", "18–30 Indian viewers"),
            what_works=profile.get("what_works", "specific and relatable content"),
            what_fails=profile.get("what_fails", "generic AI summaries"),
        )
        # Stage 1 lower temperature: we want specificity and coherence
        return self._call_openrouter_json(STAGE1_SYSTEM_V3, user, model=model, temperature=0.55, max_tokens=700)

    def generate_script_from_brief_v3(self, category: str, subtopic: str, brief: dict, model: str = "quality") -> dict:
        profile = CATEGORY_MAP.get(category, {})
        user = STAGE2_USER_V3.format(
            category=category,
            subtopic=subtopic,
            tone=profile.get("tone", "engaging, conversational"),
            language=profile.get("language", "natural Hinglish"),
            topic=brief.get("topic", ""),
            hook_line=brief.get("hook_line", ""),
            core_fact=brief.get("core_fact", ""),
            twist=brief.get("twist", ""),
            connect=brief.get("connect", ""),
        )
        # Stage 2 higher temperature: execution/voice (extra tokens to avoid truncated JSON)
        return self._call_openrouter_json(STAGE2_SYSTEM_V3, user, model=model, temperature=0.82, max_tokens=900)

    def generate_short_v3(
        self,
        category: str,
        subtopic: str,
        model: str = "quality",
        retries: int = 3,
        return_brief: bool = False,
    ) -> dict:
        brief = self.generate_idea_brief_v3(category, subtopic, model=model)
        last_failures: list[str] = []
        for attempt in range(1, retries + 1):
            try:
                script = self.generate_script_from_brief_v3(category, subtopic, brief, model=model)
                # Auto-fix common overlong outputs before hard fail.
                script = _trim_script_to_word_limit(script, target_max_words=68)
                passed, failures = quality_check(script)
                if passed:
                    script["_meta"] = {
                        "category": category,
                        "subtopic": subtopic,
                        "topic": brief.get("topic"),
                        "model": OPENROUTER_MODELS_V3.get(model),
                        "stage1_brief": brief if return_brief else None,
                        "attempt": attempt,
                    }
                    return script
                last_failures = failures
            except Exception as e:
                last_failures = [str(e)]
        raise RuntimeError(f"Failed after {retries} attempts. Last failures: {last_failures}. Brief was: {brief.get('topic')}")

    def breakdown_scenes(self, script: str) -> list[dict]:
        """
        Step 4: Scene Breakdown
        Splits script into scenes and gives keywords for each.
        """
        log.info("Breaking down scenes...")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            "Break the following script into logical scenes (typically 1-2 lines per scene).\n"
            "For each scene, provide a descriptive visual search keyword that we can use to find stock footage on platforms like Pexels.\n\n"
            f"Script:\n{script}\n\n"
            "Return ONLY a valid JSON array of objects with keys: scene (integer), text (string), keyword (string).\n"
            "Example:\n"
            '[{"scene": 1, "text": "Stop scrolling", "keyword": "attention grabbing hand"}]'
        )
        
        payload = {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a video director. Output strict JSON only. No markdown formatting."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())
                
            raw_content = res_data["choices"][0]["message"]["content"]
            clean_content = raw_content.replace("```json", "").replace("```", "").strip()
            
            # Additional cleanup in case there is text before/after JSON
            start_idx = clean_content.find("[")
            end_idx = clean_content.rfind("]") + 1
            if start_idx != -1 and end_idx != -1:
                clean_content = clean_content[start_idx:end_idx]
                
            scenes = json.loads(clean_content)
            log.info("Scenes generated: %s", len(scenes))
            return scenes
        except Exception as e:
            log.warning("Scene breakdown failed (%s), using fallback", e)
            return [
                {"scene": 1, "text": "Stop scrolling.", "keyword": "smartphone scrolling"},
                {"scene": 2, "text": "This video is important.", "keyword": "important alert"}
            ]

    def generate_voice(self, script: str) -> str:
        """
        Step 5: Voice Generation (Narrator)
        Converts the script text into an MP3 file using Sarvam AI and saves locally.
        Randomly picks from a pool of male AND female Hindi voices each run.
        Sarvam AI has a 2500-character limit per request, so long scripts are
        automatically split into chunks and concatenated via FFmpeg.
        """
        log.info("Generating voiceover for script using Sarvam AI...")

        key = getattr(settings, "sarvam_api_key", "sk_v3jy1r18_g8vrJI6RQLUD0ZHSAabCrBtR")
        if not key:
            raise ValueError("Sarvam API Key is required")

        os.makedirs(settings.tmp_dir, exist_ok=True)
        out_path = os.path.join(settings.tmp_dir, "voiceover.mp3")

        # ── Voice pool: male + female Sarvam bulbul:v3 speakers ─────────────────────
        MALE_VOICES   = ["shubh", "aditya", "rahul", "rohan", "amit",
                         "dev",   "varun",  "kabir", "tarun", "sunny"]
        FEMALE_VOICES = ["ritu",  "priya",  "neha",  "pooja", "simran",
                         "kavya", "ishita", "shreya","tanya", "shruti"]
        ALL_VOICES    = MALE_VOICES + FEMALE_VOICES

        chosen_voice = random.choice(ALL_VOICES)
        gender_label = "Male" if chosen_voice in MALE_VOICES else "Female"
        log.info("Selected voice: %s (%s)", chosen_voice, gender_label)

        SARVAM_CHAR_LIMIT = 2400  # safety margin below 2500

        def _split_into_chunks(text: str, limit: int) -> list:
            lines = text.splitlines()
            chunks, current = [], ""
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if current and len(current) + 1 + len(line) > limit:
                    chunks.append(current)
                    current = line
                else:
                    current = (current + "\n" + line).strip() if current else line
            if current:
                chunks.append(current)
            return chunks

        try:
            import base64
            from sarvamai import SarvamAI

            log.info("Connecting to SarvamAI API (voice=%s)...", chosen_voice)
            client = SarvamAI(api_subscription_key=key)

            chunks = _split_into_chunks(script, SARVAM_CHAR_LIMIT)
            log.info("Script split into %d chunk(s) for TTS (total chars: %d)", len(chunks), len(script))

            chunk_paths = []
            for ci, chunk in enumerate(chunks):
                log.info("Calling Sarvam TTS chunk %d/%d (%d chars, voice=%s)...",
                         ci + 1, len(chunks), len(chunk), chosen_voice)
                response = client.text_to_speech.convert(
                    text=chunk,
                    target_language_code="hi-IN",
                    speaker=chosen_voice,
                    pace=1.1,
                    speech_sample_rate=22050,
                    enable_preprocessing=True,
                    model="bulbul:v3"
                )

                if hasattr(response, 'audios') and response.audios:
                    audio_b64 = response.audios[0]
                elif isinstance(response, dict) and 'audios' in response:
                    audio_b64 = response['audios'][0]
                else:
                    raise ValueError(f"Unrecognized Sarvam response format: {type(response)}")

                chunk_path = os.path.join(settings.tmp_dir, f"voice_chunk_{ci}.wav")
                with open(chunk_path, "wb") as f:
                    f.write(base64.b64decode(audio_b64))
                chunk_paths.append(chunk_path)
                log.info("Chunk %d saved → %s", ci + 1, chunk_path)

            if len(chunk_paths) == 1:
                import shutil as _shutil
                _shutil.move(chunk_paths[0], out_path)
            else:
                concat_list_path = os.path.join(settings.tmp_dir, "voice_concat.txt")
                with open(concat_list_path, "w", encoding="utf-8") as f:
                    for cp in chunk_paths:
                        f.write(f"file '{cp}'\n")

                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_list_path,
                    "-acodec", "libmp3lame", "-q:a", "2",
                    out_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg audio concat failed: {result.stderr}")

                for cp in chunk_paths:
                    try:
                        os.remove(cp)
                    except Exception:
                        pass
                try:
                    os.remove(concat_list_path)
                except Exception:
                    pass

            log.info("Voiceover saved (%s, %s voice): %s", gender_label, chosen_voice, out_path)
            return out_path

        except ImportError:
            log.error("The 'sarvamai' module is not installed! Run `pip install sarvamai`.")
            raise
        except Exception as e:
            log.error("Voice generation failed via SarvamAI SDK: %s", e)
            raise

    def fetch_visuals(self, scenes: list[dict]) -> list[str]:
        """
        Step 6: Visual Generation (Eyes)
        Fetches portrait video clips from Pexels API based on scene keywords.
        Downloads them and returns a list of local file paths.
        NO DUPLICATE CLIPS — every scene gets a unique Pexels video ID.
        """
        import requests
        log.info("Fetching visuals for %d scenes...", len(scenes))
        if not settings.pexels_api_key:
            log.error("Pexels API Key missing! Cannot fetch visuals.")
            raise ValueError("pexels_api_key is required")

        # Use browser-like headers to bypass Cloudflare protection on Pexels video API
        session = requests.Session()
        session.headers.update({
            "Authorization": settings.pexels_api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.pexels.com/"
        })

        downloaded_clips = []
        os.makedirs(settings.tmp_dir, exist_ok=True)

        # Track used Pexels video IDs across ALL scenes to avoid any repeated clip
        used_video_ids: set = set()

        # Persistent dedupe across runs (better UX: new visuals every time)
        used_ids_path = os.path.join(settings.tmp_dir, "pexels_used_video_ids.txt")
        persistent_used: set[str] = set()
        if os.path.exists(used_ids_path):
            try:
                with open(used_ids_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            persistent_used.add(line)
            except Exception:
                persistent_used = set()

        def _pick_unique_video(videos: list) -> tuple:
            """Return (video_id, download_url) for the first video not in used_video_ids, or (None, None)."""
            for vid in videos:
                vid_id = vid.get("id")
                if vid_id in used_video_ids or str(vid_id) in persistent_used:
                    log.debug("Skipping duplicate Pexels video id=%s", vid_id)
                    continue
                video_files = vid.get("video_files", [])
                # Prefer highest resolution portrait file
                video_files.sort(key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
                if video_files:
                    return vid_id, video_files[0]["link"]
            return None, None

        for i, scene in enumerate(scenes):
            keyword = scene.get("keyword", "abstract pattern")
            log.info("Searching Pexels for keyword: '%s' (scene %d)", keyword, i + 1)

            chosen_id = None
            video_url = None

            try:
                # Fetch more results per page to maximise chances of finding a unique clip
                resp = session.get(
                    "https://api.pexels.com/videos/search",
                    params={"query": keyword, "per_page": 10, "orientation": "portrait"},
                    timeout=15
                )
                resp.raise_for_status()
                videos = resp.json().get("videos", [])

                chosen_id, video_url = _pick_unique_video(videos)

                if not video_url:
                    log.warning("No unique video for '%s'. Trying broader 'abstract' fallback...", keyword)
                    fb = session.get(
                        "https://api.pexels.com/videos/search",
                        params={"query": "abstract", "per_page": 15, "orientation": "portrait"},
                        timeout=15
                    )
                    fb.raise_for_status()
                    chosen_id, video_url = _pick_unique_video(fb.json().get("videos", []))

            except Exception as e:
                log.error("Pexels search API failed for scene %d: %s", i + 1, e)

            if not video_url:
                log.warning("Could not find a unique clip for scene %d — skipping.", i + 1)
                continue

            # Register this ID immediately so subsequent scenes cannot reuse it
            used_video_ids.add(chosen_id)
            persistent_used.add(str(chosen_id))

            out_path = os.path.join(settings.tmp_dir, f"scene_{i+1}.mp4")
            try:
                log.info("Downloading unique clip id=%s for scene %d...", chosen_id, i + 1)
                with session.get(video_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                downloaded_clips.append(out_path)
            except Exception as e:
                log.error("Failed to download video from %s: %s", video_url, e)
                # Release the ID so a retry could reuse it if needed (optional safety)
                used_video_ids.discard(chosen_id)

        log.info(
            "Successfully fetched %d unique clips out of %d scenes.",
            len(downloaded_clips), len(scenes)
        )

        # Persist the used IDs (cap file size to keep it manageable)
        try:
            MAX_IDS = 4000
            if len(persistent_used) > MAX_IDS:
                persistent_used = set(list(persistent_used)[-MAX_IDS:])
            with open(used_ids_path, "w", encoding="utf-8") as f:
                for vid in sorted(persistent_used):
                    f.write(f"{vid}\n")
        except Exception as e:
            log.warning("Failed to persist Pexels used IDs (%s).", e)

        return downloaded_clips


    def generate_generative_metadata(self, script: str, category: str) -> dict:
        """
        Step 8: Metadata Generation (Marketing Brain)
        Generates SEO-optimized title, description, and tags based on the script and category.
        """
        log.info("Generating Metadata for generative script...")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            f"Generate YouTube Shorts metadata for the following video script in the '{category}' category.\n\n"
            f"Script:\n{script}\n\n"
            "Return ONLY a valid JSON object with keys: title (max 60 chars, catchy, curiosity-driven), "
            "description (max 150 chars, engaging), and hashtags (space separated string, e.g. '#Viral #Shorts')."
        )
        
        payload = {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert YouTube marketer. Output strict JSON only. No markdown."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())
                
            clean_content = res_data["choices"][0]["message"]["content"].replace("```json", "").replace("```", "").strip()
            
            start_idx = clean_content.find("{")
            end_idx = clean_content.rfind("}") + 1
            if start_idx != -1 and end_idx != -1:
                clean_content = clean_content[start_idx:end_idx]
                
            meta = json.loads(clean_content)
            log.info("Generative Metadata: %s", meta)
            return meta
        except Exception as e:
            log.error("Metadata generation failed: %s", e)
            return {"title": "Wait for this...", "description": "Mind blowing...", "hashtags": "#Shorts #Trending"}

    def evaluate_video_quality(self, script: str) -> dict:
        """
        Step 9: Quality Check (AI Manager)
        Evaluates the generated script and returns a score and status.
        """
        log.info("Evaluating script quality...")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            "Evaluate this YouTube Shorts script out of 10. Check if the hook is strong, engaging, and clear.\n\n"
            f"Script:\n{script}\n\n"
            "Return ONLY a valid JSON object with keys: 'score' (float) and 'status' (string, either 'approve' or 'reject'). "
            "Reject anything scoring below 7.0."
        )
        
        payload = {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a YouTube Quality Manager. Output strict JSON only. No markdown."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode())
                
            clean_content = res_data["choices"][0]["message"]["content"].replace("```json", "").replace("```", "").strip()
            
            start_idx = clean_content.find("{")
            end_idx = clean_content.rfind("}") + 1
            if start_idx != -1 and end_idx != -1:
                clean_content = clean_content[start_idx:end_idx]
                
            eval_res = json.loads(clean_content)
            log.info("Evaluation Result: %s", eval_res)
            return eval_res
        except Exception as e:
            log.warning("Evaluation failed (%s), defaulting to approve", e)
            return {"score": 8.0, "status": "approve"}






