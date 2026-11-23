from django.db import migrations, models

SCAN_CHOICES = [
    ("pending", "Pending"),
    ("clean", "Clean"),
    ("infected", "Infected"),
    ("damaged", "Damaged"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0002_attachment_name_fulltext"),
    ]

    # Files already stored are plain and were shared before scanning, so they start as
    # unencrypted and clean; new rows then get the model's defaults.
    operations = [
        migrations.AddField(
            model_name="attachment",
            name="encrypted",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="attachment",
            name="encrypted",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="attachment",
            name="scan",
            field=models.CharField(choices=SCAN_CHOICES, default="clean", max_length=10),
        ),
        migrations.AlterField(
            model_name="attachment",
            name="scan",
            field=models.CharField(choices=SCAN_CHOICES, default="pending", max_length=10),
        ),
        migrations.AddField(
            model_name="attachment",
            name="scan_detail",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="attachment",
            name="scanned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
