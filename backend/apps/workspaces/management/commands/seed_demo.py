"""Two invented teams with a few months of conversations and issues, for demos and screenshots.

    python manage.py seed_demo --password "something long"
    python manage.py seed_demo --reset    # remove them and seed again

People sign in with handle@team.example (see apps/workspaces/demo_content.py) and the password.
"""

import secrets

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.workspaces import demo
from apps.workspaces.demo_content import TEAMS


class Command(BaseCommand):
    help = "Seed two invented teams with conversations and issues."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--password", help="For every seed user; made up and printed if left out."
        )
        parser.add_argument("--days", type=int, default=120, help="How far back the history goes.")
        parser.add_argument("--seed", type=int, default=7, help="Same seed, same data.")
        parser.add_argument(
            "--reset", action="store_true", help="Remove the demo teams and their people first."
        )

    def handle(self, *args: object, **options: object) -> None:
        if options["reset"]:
            demo.remove()
        clashes = demo.existing()
        if clashes:
            raise CommandError(
                "Already there: " + ", ".join(clashes) + ". Use --reset to replace the demo teams."
            )
        password = str(options["password"] or secrets.token_urlsafe(12))
        days = int(str(options["days"]))
        for workspace in demo.seed(password, days, int(str(options["seed"]))):
            self.stdout.write(f"Seeded /w/{workspace.slug}")
        for team in TEAMS:
            people = ", ".join(demo.email_of(p.handle, team) for p in team.people)
            self.stdout.write(f"{team.name}: {people}")
        if not options["password"]:
            self.stdout.write(f"Password for all of them: {password}")
