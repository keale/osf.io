# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-03-12 18:25
from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.db import migrations
from django.db.models import F
from django.db.models import OuterRef, Subquery

from itertools import islice, chain


def batch(iterable, size):
    sourceiter = iter(iterable)
    while True:
        batchiter = islice(sourceiter, size)
        yield chain([batchiter.next()], batchiter)


def divorce_preprints_from_nodes(apps, schema_editor):
    Preprint = apps.get_model('osf', 'PreprintService')
    AbstractNode = apps.get_model('osf', 'AbstractNode')
    PreprintContributor = apps.get_model('osf', 'PreprintContributor')

    node_subquery = AbstractNode.objects.filter(preprints=OuterRef('pk')).order_by('-created')
    Preprint.objects.annotate(
        node_title=Subquery(node_subquery.values('title')[:1])).annotate(
        node_description=Subquery(node_subquery.values('description')[:1])).annotate(
        node_creator=Subquery(node_subquery.values('creator')[:1])).update(
        title=F('node_title'),
        description=F('node_description'),
        creator=F('node_creator')
    )

    contributors = []

    for preprint in Preprint.objects.filter(node__isnull=False):
        # use bulk create
        admin = []
        write = []
        read = []
        for contrib in preprint.node.contributor_set.all():
            # make a PreprintContributor that points to the pp instead of the node
            # because there's a throughtable, relations are designated
            # solely on the through model, and adds on the related models
            # are not required.

            new_contrib = PreprintContributor(
                preprint_id=preprint.id,
                user_id=contrib.user.id,
                visible=contrib.visible,
                _order=contrib._order
            )
            contributors.append(new_contrib)
            if contrib.admin:
                admin.append(contrib.user)
            elif contrib.write:
                write.append(contrib.user)
            else:
                read.append(contrib.user)
        preprint.get_group('admin').user_set.add(admin)
        preprint.get_group('write').user_set.add(write)
        preprint.get_group('read').user_set.add(read)
        preprint.save()

    batch_size = 1000
    while True:
        batch = list(islice(contributors, batch_size))
        if not batch:
            break
        PreprintContributor.objects.bulk_create(batch, batch_size)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0083_update_preprint_model_for_divorce'),
    ]

    operations = [
        migrations.RunPython(divorce_preprints_from_nodes)
    ]
