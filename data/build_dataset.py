"""
Builds data/tickets.csv -- a synthetic support-ticket dataset (5 labels).

Synthetic on purpose: it lets the whole pipeline be demoed with no private
data. Each ticket = optional opener + core sentence + optional closer, so the
model sees varied phrasing instead of ~8 memorisable rows. Swap this for real
tickets (e.g. an export from a helpdesk) by replacing data/tickets.csv with
the same two columns: text,label.

Run:  python3 data/build_dataset.py
"""
import csv
import random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent / "tickets.csv"

CORE = {
    "bug": [
        "the app keeps crashing when I upload a photo",
        "checkout button does nothing on mobile Safari",
        "I get a blank white screen after logging in",
        "the page freezes whenever I open the settings tab",
        "notifications are not showing up even though they are enabled",
        "search returns an error 500 every time",
        "my profile picture disappears after I refresh",
        "the export to PDF produces an empty file",
        "the app is stuck on the loading spinner forever",
        "dark mode makes the text unreadable in the sidebar",
        "I cannot save changes, the save button just spins",
        "the video player stops after ten seconds",
        "buttons overlap each other on my tablet",
        "the date picker shows the wrong month",
        "uploads fail at 99 percent with a network error",
        "the app logs me out every few minutes",
    ],
    "billing": [
        "can I get a refund for my last order",
        "I was charged twice for the same subscription",
        "why did my invoice go up this month",
        "please cancel my subscription before the next billing date",
        "my card was declined but the money left my account",
        "I need a receipt for my payment last week",
        "the coupon code was not applied at checkout",
        "how do I update the credit card on my account",
        "I was billed after I already cancelled",
        "can you switch me from monthly to annual billing",
        "there is an unknown charge on my statement from your company",
        "the tax amount on my invoice looks wrong",
        "I upgraded my plan but I was not credited for the unused time",
        "my payment is stuck as pending for three days",
        "do you offer a student discount",
        "I want to downgrade my plan and get the difference back",
    ],
    "praise": [
        "love the new dark mode, great update",
        "this is the best app I have used all year",
        "the new dashboard is fantastic, so clean and fast",
        "your support team solved my issue in minutes, amazing",
        "thank you, this saved me hours of work every week",
        "the latest release is super smooth, well done",
        "I recommend this to all my friends, brilliant product",
        "the design is beautiful and really easy to use",
        "whoever built the search feature deserves a raise",
        "five stars, it does exactly what I need",
        "the onboarding was delightful, nicely done",
        "huge thanks to the team for the quick fix",
        "I am impressed by how fast everything loads now",
        "keep up the great work, I use it every day",
        "the new layout is a huge improvement, thank you",
        "really happy with the update, everything feels polished",
    ],
    "support": [
        "how do I reset my password",
        "where do I change my email address",
        "how can I add a teammate to my workspace",
        "is there a way to export all my data",
        "how do I turn off email notifications",
        "I forgot which email I signed up with",
        "can you explain how the sharing permissions work",
        "how do I delete my account",
        "where can I find the API documentation",
        "how do I connect my calendar",
        "what is the difference between the free and pro plans",
        "how do I recover a project I deleted by mistake",
        "can I use the app on two devices at once",
        "how do I enable two factor authentication",
        "where is the option to change the language",
        "is there a guide for getting started",
    ],
    "feature_request": [
        "it would be great if you added a keyboard shortcut for search",
        "please add support for exporting to CSV",
        "can you add an option to schedule posts",
        "I wish there was a dark theme for the mobile app",
        "would love to see integration with Slack",
        "please consider adding bulk editing",
        "it would help a lot to have an offline mode",
        "could you add a way to tag items with colors",
        "we need role based permissions for larger teams",
        "please let us customize the dashboard widgets",
        "an undo button would be really useful",
        "can you support sign in with Google",
        "add an option to duplicate a project please",
        "I would like a weekly summary email of my activity",
        "it would be nice to have a calendar view",
        "please add a public API so we can automate this",
    ],
}

OPENERS = ["", "", "", "Hi, ", "Hello team, ", "Hey, ", "Quick question: ", "Good morning, ", "Hi there, ", "Urgent: "]
CLOSERS = ["", "", "", ".", "!", " - thanks", ", please help", " as soon as possible", ", any ideas?", " on my phone", " since yesterday", " on the web version"]


def make(core: str) -> str:
    text = random.choice(OPENERS) + core + random.choice(CLOSERS)
    text = text[0].upper() + text[1:] if not text[0].isupper() else text
    return text.strip()


def main():
    rows = []
    for label, cores in CORE.items():
        seen = set()
        for core in cores:
            for _ in range(5):          # up to 5 phrasings per core sentence
                t = make(core)
                if t not in seen:
                    seen.add(t)
                    rows.append((t, label))
    random.shuffle(rows)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "label"])
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
