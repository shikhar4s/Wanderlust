from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0006_destination_region')]

    operations = [
        migrations.AddField(
            model_name='place',
            name='image_kind',
            field=models.CharField(blank=True, max_length=16),
        ),
    ]
