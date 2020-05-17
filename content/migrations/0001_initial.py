# Generated by Django 3.0.6 on 2020-05-17 10:54

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='news',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Feature', max_length=200)),
                ('text', models.CharField(max_length=10000)),
                ('synopsis', models.CharField(default='', max_length=1000)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('updated_date', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(choices=[('d', 'Draft'), ('p', 'Published'), ('w', 'Withdrawn')], default='d', max_length=1)),
                ('published_date', models.DateTimeField(auto_now=True, null=True)),
            ],
        ),
    ]
