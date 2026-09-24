from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0005_destination_places_synced_at')]

    operations = [
        migrations.AddField(
            model_name='destination',
            name='region',
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.RemoveConstraint(model_name='destination', name='unique_destination'),
        migrations.AddConstraint(
            model_name='destination',
            constraint=models.UniqueConstraint(fields=('name', 'country', 'region'), name='unique_destination_region'),
        ),
    ]
