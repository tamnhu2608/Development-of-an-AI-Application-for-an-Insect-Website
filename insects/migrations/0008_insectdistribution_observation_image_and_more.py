from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('insects', '0007_insectdistribution_observation_image_and_more'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='distributionboundingbox',
            table='distribution_bbox',
        ),
    ]
