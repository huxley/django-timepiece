import datetime
from dateutil.relativedelta import relativedelta
from random import randrange
from urllib import urlencode

from django.contrib.auth.models import User, Permission
from django.core.urlresolvers import reverse

try:
    from django.utils import timezone
except ImportError:
    from timepiece import timezone

from timepiece import utils
from timepiece.models import Entry, ProjectHours
from timepiece.tests.base import TimepieceDataTestCase


class DashboardViewTestCase(TimepieceDataTestCase):
    """Tests the data that is passed to the dashboard template."""

    def setUp(self):
        self.today = datetime.date(2012, 11, 7)
        self.this_week = utils.get_week_start(self.today)
        self.next_week = self.this_week + relativedelta(days=7)

        get_params = {'week_start': self.this_week.strftime('%Y-%m-%d')}
        self.url = reverse('dashboard') + '?' + urlencode(get_params)

        self.uname = 'test'
        self.pword = 'password'
        self.user = self.create_user(username=self.uname, password=self.pword)
        self.permission = Permission.objects.get(codename='can_clock_in')
        self.user.user_permissions.add(self.permission)
        self.client.login(username=self.uname, password=self.pword)

        self.project = self.create_project()
        self.activity = self.create_activity()
        self.location = self.create_location()
        self.status = 'unverified'

    def _create_entry(self, start_time, end_time=None, user=None):
        """
        Creates an entry using default values. If end time is not given, the
        entry is considered active.
        """
        data = {
            'user': user or self.user,
            'project': self.project,
            'activity': self.activity,
            'location': self.location,
            'status': self.status,
            'start_time': start_time,
        }
        if end_time:
            data['end_time'] = end_time
        return self.create_entry(data=data)

    def _create_active_entry(self):
        start_time = datetime.datetime(2012, 11, 9, 0)
        return self._create_entry(start_time)

    def _create_entries(self):
        count = 5
        start_time = datetime.datetime(2012, 11, 5, 8)
        end_time = datetime.datetime(2012, 11, 5, 12)
        for i in range(count):
            start_time = end_time + relativedelta(seconds=1)
            end_time += relativedelta(hours=4)
            self._create_entry(start_time, end_time)
        return count

    def _create_others_entries(self):
        count = 5
        start_time = datetime.datetime(2012, 11, 6, 12)
        for i in range(count):
            user = self.create_user()
            self._create_entry(start_time, user=user)
        return count

    def test_unauthenticated_user(self):
        """Unauthenticated users should be redirected to login view."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_unprivileged_user(self):
        """Unprivileged users should not see any content."""
        self.user.user_permissions.remove(self.permission)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # TODO: better test for whether this is working.

    def test_get(self):
        """Get without param gets entries for this week."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['week_start'],
                utils.get_week_start().date())
        self.assertEqual(response.context['week_end'],
                utils.get_week_start().date() + relativedelta(days=6))

    def test_active_entry(self):
        """Active entry should be given if it exists."""
        active_entry = self._create_active_entry()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_entry'], active_entry)

    def test_no_active_entry(self):
        """Active entry should be None if it doesn't exist."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_entry'], None)

    def test_weeks_entries(self):
        """Week's entries list should include active entry."""
        entry_count = self._create_entries()
        active_entry = self._create_active_entry()
        entry_count += 1
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(active_entry in response.context['week_entries'])
        self.assertEqual(len(response.context['week_entries']), entry_count)

    def test_no_weeks_entries(self):
        """Week's entries list should be empty if no entries this week."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['week_entries']), 0)

    def test_other_active_entries(self):
        """Others' entries list should exclude this user's active entry."""
        entry_count = self._create_others_entries()
        active_entry = self._create_active_entry()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        others_active_entries = response.context['others_active_entries']
        self.assertFalse(active_entry in others_active_entries)
        self.assertEqual(len(others_active_entries), entry_count)

    def test_no_other_active_entries(self):
        """Others' entries list should be empty if no other active entries."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['others_active_entries']), 0)


class ProcessProgressTestCase(TimepieceDataTestCase):
    """Tests for timepiece.utils.process_progress."""

    def setUp(self):
        self.today = datetime.date(2012, 11, 7)
        self.this_week = utils.get_week_start(self.today)
        self.next_week = self.this_week + relativedelta(days=7)

        self.uname = 'test'
        self.pword = 'password'
        self.user = self.create_user(username=self.uname, password=self.pword)
        self.client.login(username=self.uname, password=self.pword)

        self.project = self.create_project()
        self.activity = self.create_activity()
        self.location = self.create_location()
        self.status = 'unverified'

    def _create_entry(self, start_time, end_time=None, project=None):
        data = {
            'user': self.user,
            'project': project or self.project,
            'activity': self.activity,
            'location': self.location,
            'status': self.status,
            'start_time': start_time,
        }
        if end_time:
            data['end_time'] = end_time
        return self.create_entry(data=data)

    def _create_hours(self, hours, project=None):
        data = {
            'user': self.user,
            'project': project or self.project,
            'week_start': self.this_week,
            'hours': hours,
        }
        return self.create_project_hours_entry(**data)

    def _get_progress(self):
        entries = Entry.objects.all()
        assignments = ProjectHours.objects.all()
        return utils.process_progress(entries, assignments)

    def _check_progress(self, progress, project, assigned, worked):
        self.assertEqual(progress['project'], project)
        self.assertEqual(progress['assigned'], assigned)
        self.assertEqual(progress['worked'], worked)

    def test_progress(self):
        """Progress when work has been done for an assigned project."""
        start_time = datetime.datetime(2012, 11, 7, 8, 0)
        end_time = datetime.datetime(2012, 11, 7, 12, 0)
        entry = self._create_entry(start_time, end_time)
        worked_hours = 4
        assigned_hours = 5
        assignment = self._create_hours(assigned_hours)

        progress = self._get_progress()
        self.assertEqual(len(progress), 1)
        self._check_progress(progress[0], self.project,
                assigned_hours, worked_hours)

    def test_work_with_no_assignment(self):
        """Progress when work has been done on an unassigned project."""
        start_time = datetime.datetime(2012, 11, 7, 8, 0)
        end_time = datetime.datetime(2012, 11, 7, 12, 0)
        entry = self._create_entry(start_time, end_time)
        worked_hours = 4

        progress = self._get_progress()
        self.assertEqual(len(progress), 1)
        self._check_progress(progress[0], self.project, 0, worked_hours)

    def test_assignment_with_no_work(self):
        """Progress when no work has been done on an assigned project."""
        assigned_hours = 5
        assignment = self._create_hours(assigned_hours)

        progress = self._get_progress()
        self.assertEqual(len(progress), 1)
        self._check_progress(progress[0], self.project, assigned_hours, 0)

    def test_ordering(self):
        """Progress list should be ordered by project name."""
        projects = [
            self.create_project(data={'name': 'a'}),
            self.create_project(data={'name': 'b'}),
            self.create_project(data={'name': 'c'}),
        ]
        for i in range(3):
            start_time = datetime.datetime(2012, 11, 5 + i, 8, 0)
            end_time = datetime.datetime(2012, 11, 5 + i, 12, 0)
            entry = self._create_entry(start_time, end_time, projects[i])
            assignment = self._create_hours(5 + 5 * i, projects[i])

        progress = self._get_progress()
        self.assertEqual(len(progress), 3)
        self.assertEqual(progress[0]['project'], projects[0])
        self.assertEqual(progress[1]['project'], projects[1])
        self.assertEqual(progress[2]['project'], projects[2])


class AjaxTogglePauseTestCase(TimepieceDataTestCase):
    url_name = 'ajax_toggle_pause'
    perm_names = [('timepiece', 'can_pause')]

    def setUp(self):
        get_perm = lambda ct, n: Permission.objects.get(
                content_type__app_label=ct, codename=n)
        self.permissions = [get_perm(*perm) for perm in self.perm_names]

        self.username = self.random_string(25)
        self.password = self.random_string(25)
        self.email = self.random_string(25) + '@example.com'
        self.user = self.create_user(self.username, self.email, self.password)
        self.user.user_permissions.add(*self.permissions)
        self.client.login(username=self.username, password=self.password)

        self.active_entry = self.create_entry(data={
            'start_time': datetime.datetime(2012, 2, 1, 12, 0),
        })

    def test_login_required(self):
        self.client.logout()
        response = self._post()
        self.assertEqual(response.status_code, 302)

    def test_permission_required(self):
        self.user.user_permissions.all().delete()
        response = self._post()
        self.assertEqual(response.status_code, 302)

    def test_get(self):
        response = self._get()
        self.assertEqual(response.status_code, 405)

    def test_no_active_entry(self):
        self.active_entry.delete()
        response = self._post()
        self.assertEqual(response.status_code, 404)

    def test_pause(self):
        self.active_entry.unpause()
        self.active_entry.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Entry.objects.get().is_paused)

    def test_unpause(self):
        self.active_entry.pause()
        self.active_entry.save()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Entry.objects.get().is_paused)
