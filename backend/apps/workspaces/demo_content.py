"""Invented teams for `manage.py seed_demo`. Every person, line and issue here is made up.

{who} in a line becomes an @mention of someone else in the channel.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Person:
    handle: str
    name: str
    role: str = "member"


@dataclass(frozen=True)
class ChannelPlan:
    name: str
    topic: str
    lines: list[str]
    private: bool = False
    # Handles; empty means everyone but guests.
    members: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Team:
    name: str
    slug: str
    people: list[Person]
    channels: list[ChannelPlan]
    project_key: str
    project_name: str
    labels: list[tuple[str, str]]
    issues: list[str]


REPLIES = [
    "On it.",
    "Agreed, let's do that.",
    "I can take this after lunch.",
    "Good catch, thanks.",
    "Can we talk about it in standup?",
    "Done, have a look when you get a minute.",
    "Not sure, {who} would know better.",
    "Same here, I saw it yesterday too.",
    "Pushed a fix, should be better now.",
    "Let's keep it simple for now and revisit next week.",
    "+1",
    "Makes sense to me.",
]

GENERAL = [
    "Good morning everyone.",
    "Reminder: team lunch is on Thursday, biryani from the usual place.",
    "Office internet is down again, working from the cafe for an hour.",
    "Who has the meeting room booked at 3?",
    "Welcome to the team, {who}!",
    "Load shedding schedule changed, 2 to 4 pm in our area this week.",
    "Friday is a half day for Eid prep, plan accordingly.",
    "Can someone share the notes from yesterday's call?",
    "Chai is ready in the kitchen.",
    "Heads up: the parking gate code changed.",
]

RANDOM = [
    "Anyone watching the match tonight?",
    "Best nihari in town, go.",
    "It finally rained, the whole street is a river.",
    "Recommendations for a mechanical keyboard that isn't too loud?",
    "My cat walked across the keyboard and pushed to a branch. Not even joking.",
    "Weekend plans: sleeping and more sleeping.",
    "Found a great bookshop in Saddar, will share the location.",
    "Who wants to join a cricket game on Sunday morning?",
]

CHAI_CODE = Team(
    name="Chai and Code",
    slug="chai-and-code",
    people=[
        Person("amna", "Amna Khan", "owner"),
        Person("omar", "Omar Farooq", "admin"),
        Person("bilal", "Bilal Ahmed"),
        Person("sana", "Sana Mirza"),
        Person("hamza", "Hamza Qureshi"),
        Person("zara", "Zara Hussain"),
        Person("fatima", "Fatima Noor"),
        Person("daniel", "Daniel Brooks", "guest"),
    ],
    channels=[
        ChannelPlan("general", "Company news and everyday things", GENERAL),
        ChannelPlan(
            "dev",
            "Builds, reviews and broken things",
            [
                "The staging deploy failed again, looking into it.",
                "{who} can you review my pull request when you get a chance?",
                "Upgrading the database driver today, expect a short restart.",
                "Tests are flaky on CI, the upload test times out sometimes.",
                "Is anyone else seeing the login page load slowly?",
                "Merged the search changes, please pull before you start.",
                "Who owns the payments service now?",
                "The memory leak was a cache that never expired. Fixed.",
                "Should we move the cron jobs to the task queue?",
                "Release notes for 2.4 are in the doc, add anything I missed.",
                "{who} the API returns 500 when the date is empty, can you check?",
                "Pair on the migration this afternoon?",
            ],
        ),
        ChannelPlan(
            "design",
            "Screens, type and colours",
            [
                "New onboarding screens are up for feedback.",
                "{who} the button contrast on dark mode is too low.",
                "Trying a warmer accent colour, thoughts?",
                "Icons exported, they're in the shared folder.",
                "The empty states need copy, who writes them?",
                "Usability test tomorrow with three people from the client side.",
                "Mobile nav feels crowded, I'll try a bottom bar.",
            ],
        ),
        ChannelPlan("random", "Anything else", RANDOM),
        ChannelPlan(
            "client-bazaar",
            "Shared with the Bazaar team",
            [
                "Hi all, the checkout redesign is ready for review on staging.",
                "Daniel, can you confirm the delivery fee rules for outside the city?",
                "We'll ship the order tracking page next Tuesday.",
                "Thanks, the team loved the new product pages.",
                "Is the holiday sale banner still going live on the 20th?",
                "Invoices for last month are in your inbox.",
            ],
            members=["amna", "omar", "sana", "bilal", "daniel"],
        ),
        ChannelPlan(
            "leads",
            "Hiring, planning and budgets",
            [
                "Two strong candidates for the backend role, interviews this week.",
                "Q3 budget is approved, with one more hire.",
                "We should plan the offsite before the monsoon.",
                "Client asked for a fixed price on phase two, let's discuss.",
            ],
            private=True,
            members=["amna", "omar"],
        ),
    ],
    project_key="BAZ",
    project_name="Bazaar app",
    labels=[("bug", "danger"), ("feature", "accent"), ("design", "ember"), ("ops", "info")],
    issues=[
        "Checkout fails when the cart has more than 20 items",
        "Add order tracking page",
        "Search ignores Urdu product names",
        "Dark mode contrast on buttons",
        "Move image resizing to the task queue",
        "Password reset email goes to spam",
        "Delivery fee rules for outside Karachi",
        "Holiday sale banner",
        "Slow product page on 3G",
        "Crash when the profile photo is a HEIC file",
        "Export orders as a spreadsheet",
        "Upgrade the database driver",
        "Empty states need copy",
        "Mobile navigation feels crowded",
    ],
)

MONSOON_PRESS = Team(
    name="Monsoon Press",
    slug="monsoon-press",
    people=[
        Person("ayesha", "Ayesha Siddiqui", "owner"),
        Person("kamran", "Kamran Ali", "admin"),
        Person("nida", "Nida Rehman"),
        Person("usman", "Usman Tariq"),
        Person("mehwish", "Mehwish Javed"),
        Person("ali", "Ali Raza"),
        Person("leila", "Leila Haddad", "guest"),
    ],
    channels=[
        ChannelPlan("general", "Everything for everyone", GENERAL),
        ChannelPlan(
            "newsroom",
            "Today's stories",
            [
                "Budget story needs one more source, {who} can you call the ministry?",
                "Photos from the flood coverage are in, they're strong.",
                "Front page meeting at 11.",
                "The transport strike piece is filed, ready for edits.",
                "{who} the headline is too long for mobile.",
                "We have a correction on yesterday's market story.",
                "Interview with the mayor moved to Thursday.",
                "Breaking: power outage across the east of the city.",
                "Who's covering the book fair this weekend?",
            ],
        ),
        ChannelPlan(
            "edits",
            "Copy desk",
            [
                "Style question: do we write per cent or percent?",
                "Cut 200 words from the education feature.",
                "{who} please check the spelling of the minister's name.",
                "The long read is on the copy desk now.",
                "Numbers in the chart don't match the text.",
            ],
        ),
        ChannelPlan(
            "photos",
            "Pictures and permissions",
            [
                "Leila sent the market series, picking six.",
                "We need a credit line for the archive photo.",
                "Drone shots of the coastline are uploading.",
                "{who} can you caption the protest set?",
            ],
            members=["ayesha", "kamran", "mehwish", "ali", "leila"],
        ),
        ChannelPlan("random", "Off topic", RANDOM),
    ],
    project_key="WEB",
    project_name="Website",
    labels=[("bug", "danger"), ("feature", "accent"), ("editorial", "warning")],
    issues=[
        "Live blog page for the election",
        "Photo captions cut off on mobile",
        "Newsletter sign-up form",
        "Corrections page",
        "Paywall counts articles twice",
        "Author pages with bios",
        "Search results show drafts",
        "Faster article pages on slow connections",
        "Urdu headlines break the layout",
        "Archive pages before 2015 are missing images",
    ],
)

TEAMS = [CHAI_CODE, MONSOON_PRESS]

# Code point escapes, as in frontend/src/chat/reactions.ts.
REACTIONS = ["\U0001f44d", "❤️", "\U0001f602", "\U0001f389", "\U0001f440", "✅"]
