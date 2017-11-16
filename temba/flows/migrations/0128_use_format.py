# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-10-19 18:14
from __future__ import unicode_literals

from django.db import migrations
import re
import json


def use_format_date(apps, schema_editor):
    from temba.flows.models import RuleSet, ActionSet, Flow
    from temba.contacts.models import ContactField

    # find all rulesets that are date or location
    rulesets = RuleSet.objects.filter(flow__is_active=True, value_type__in=['D', 'S', 'I', 'W']).select_related('flow')

    for dr in rulesets:
        # make sure or flow this flow is migrated forward
        dr.flow.ensure_current_version()

        # determine our slug
        slug = Flow.label_to_slug(dr.label)
        changed = False

        # dates will be wrapped in format_date, locations in format_location
        format_function = 'format_date' if dr.value_type == 'D' else 'format_location'

        # find plain references to this field in actionsets, we'll replace them with a format wrapper
        for ac in ActionSet.objects.filter(flow=dr.flow, actions__icontains="@flow." + slug):
            pattern = "@flow\\." + slug + "([^0-9a-zA-Z\\.]|\.[^0-9a-zA-Z\\.])"
            if re.search(pattern, ac.actions, flags=re.UNICODE | re.MULTILINE):
                orig = ac.actions
                try:
                    json_actions = json.loads(ac.actions)
                    for i, json_action in enumerate(json_actions):
                        if json_action['type'] in ['reply', 'send', 'say']:
                            json_actions[i] = json.loads(
                                re.sub(
                                    pattern,
                                    "@(%s(flow.%s))\\1" % (format_function, slug),
                                    json.dumps(json_action),
                                    flags=re.UNICODE | re.MULTILINE
                                )
                            )

                    ac.actions = json.dumps(json_actions)
                    ac.save(update_fields=['actions'])
                    print("actionset(%d) replaced:\n%s\nwith:\n%s" % (ac.id, orig, ac.actions))
                    changed = True

                except Exception:
                    import traceback
                    traceback.print_exc()
                    print("unable to parse actionset(%d): %s" % (ac.id, ac.actions))

        # create a new revision from this definition if things changed
        if changed:
            dr.flow.update(dr.flow.as_json())

    # for every contact field that is a date or location and has dependencies
    for cf in ContactField.objects.filter(is_active=True, value_type__in=['D', 'S', 'I', 'W']).exclude(dependent_flows=None):
        format_function = 'format_date' if cf.value_type == 'D' else 'format_location'

        # find plain references to this field in actionsets, we'll replace them with format_date
        for flow in cf.dependent_flows.all():
            # make sure this flow is the current version
            flow.ensure_current_version()

            changed = False
            for ac in ActionSet.objects.filter(flow=dr.flow, actions__icontains="@contact." + cf.key):
                pattern = "@contact\\." + cf.key + "([^0-9a-zA-Z\\.]|\.[^0-9a-zA-Z\\.])"
                if re.search(pattern, ac.actions, flags=re.UNICODE | re.MULTILINE):
                    orig = ac.actions
                    try:
                        json_actions = json.loads(ac.actions)
                        for i, json_action in enumerate(json_actions):
                            if json_action['type'] in ['reply', 'send', 'say']:
                                json_actions[i] = json.loads(
                                    re.sub(
                                        pattern,
                                        "@(%s(contact.%s))\\1" % (format_function, cf.key),
                                        json.dumps(json_action),
                                        flags=re.UNICODE | re.MULTILINE
                                    )
                                )

                        ac.actions = json.dumps(json_actions)
                        ac.save(update_fields=['actions'])
                        print("actionset(%d) replaced:\n%s\nwith:\n%s" % (ac.id, orig, ac.actions))
                        changed = True

                    except Exception:
                        import traceback
                        traceback.print_exc()
                        print("unable to parse actionset(%d): %s" % (ac.id, ac.actions))

            # create a new revision from this definition if things changed
            if changed:
                flow.update(dr.flow.as_json())


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0127_backfill_flowrun_path'),
    ]

    operations = [
        migrations.RunPython(use_format_date)
    ]
