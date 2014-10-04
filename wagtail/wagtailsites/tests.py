from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse

from wagtail.tests.utils import WagtailTestUtils
from wagtail.wagtailcore.models import Site, Page
import six


class TestSiteIndexView(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()
        self.home_page = Page.objects.get(id=2)

    def get(self, params={}):
        return self.client.get(reverse('wagtailsites_index'), params)

    def test_simple(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailsites/index.html')

    def test_pagination(self):
        pages = ['0', '1', '-1', '9999', 'Not a page']
        for page in pages:
            response = self.get({'p': page})
            self.assertEqual(response.status_code, 200)


class TestSiteCreateView(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()
        self.home_page = Page.objects.get(id=2)
        self.localhost = Site.objects.all()[0]

    def get(self, params={}):
        return self.client.get(reverse('wagtailsites_create'), params)

    def post(self, post_data={}):
        return self.client.post(reverse('wagtailsites_create'), post_data)

    def create_site(self, hostname='testsite', port=80, is_default_site=False, root_page=None):
        root_page = root_page or self.home_page
        Site.objects.create(
            hostname=hostname,
            port=port,
            is_default_site=is_default_site,
            root_page=root_page)

    def test_default_fixtures_present(self):
        # we should have loaded with a single site
        self.assertEqual(self.localhost.hostname, 'localhost')
        self.assertEqual(self.localhost.port, 80)
        self.assertEqual(self.localhost.is_default_site, True)
        self.assertEqual(self.localhost.root_page, self.home_page)

    def test_simple(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailsites/create.html')

    def test_create(self):
        response = self.post({
            'hostname': "testsite",
            'port': "80",
            'root_page': str(self.home_page.id),
        })

        # Should redirect back to index
        self.assertRedirects(response, reverse('wagtailsites_index'))

        # Check that the site was created
        self.assertEqual(Site.objects.filter(hostname='testsite').count(), 1)

    def test_duplicate_defaults_not_allowed(self):
        response = self.post({
            'hostname': "also_default",
            'port': "80",
            'is_default_site': "on",
            'root_page': str(self.home_page.id),
        })

        # Should return the form with errors
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bool(response.context['form'].errors), True)

        # Check that the site was not created
        sites = Site.objects.filter(hostname='also_default')
        self.assertEqual(sites.count(), 0)

    def test_duplicate_hostnames_on_different_ports_allowed(self):
        response = self.post({
            'hostname': "localhost",
            'port': "8000",
            'root_page': str(self.home_page.id),
        })

        # Should redirect back to index
        self.assertRedirects(response, reverse('wagtailsites_index'))

        # Check that the site was created
        self.assertEqual(Site.objects.filter(hostname='localhost').count(), 2)

    def test_duplicate_hostnames_on_same_port_not_allowed(self):
        # Confirm there's one localhost already
        self.assertEqual(Site.objects.filter(hostname='localhost').count(), 1)

        response = self.post({
            'hostname': "localhost",
            'port': "80",
            'root_page': str(self.home_page.id),
        })

        # Should return the form with errors
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bool(response.context['form'].errors), True)

        # Check that the site was not created, still only one localhost entry
        self.assertEqual(Site.objects.filter(hostname='localhost').count(), 1)


class TestSiteEditView(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()
        self.home_page = Page.objects.get(id=2)
        self.localhost = Site.objects.all()[0]

    def get(self, params={}, site_id=None):
        return self.client.get(reverse('wagtailsites_edit', args=(site_id or self.localhost.id, )), params)

    def post(self, post_data={}, site_id=None):
        site_id = site_id or self.localhost.id
        site = Site.objects.get(id=site_id)
        post_defaults = {
            'hostname': site.hostname,
            'port': site.port,
            'root_page': site.root_page.id,
        }
        for k, v in six.iteritems(post_defaults):
            post_data[k] = post_data.get(k, v)
        if 'default' in post_data:
            if post_data['default']:  # only include the is_default_site key if we want to set it
                post_data['is_default_site'] = 'on'
        elif site.is_default_site:
            post_data['is_default_site'] = 'on'
        return self.client.post(reverse('wagtailsites_edit', args=(site_id,)), post_data)

    def test_simple(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailsites/edit.html')

    def test_nonexistant_redirect(self):
        self.assertEqual(self.get(site_id=100000).status_code, 404)

    def test_edit(self):
        edited_hostname = 'edited'
        response = self.post({
            'hostname': edited_hostname,
        })

        # Should redirect back to index
        self.assertRedirects(response, reverse('wagtailsites_index'))

        # Check that the site was edited
        self.assertEqual(Site.objects.get(id=self.localhost.id).hostname, edited_hostname)

    def test_changing_the_default_site_workflow(self):
        # First create a second, non-default, site
        second_site = Site.objects.create(
            hostname="not_yet_default",
            port=80,
            is_default_site=False,
            root_page=self.home_page)

        # Make the original default no longer default
        response = self.post(
            {
                'default': False,
            },
            site_id=self.localhost.id
        )

        # Should redirect back to index
        self.assertRedirects(response, reverse('wagtailsites_index'))
        # Check that the site is no longer default
        self.assertEqual(Site.objects.get(id=self.localhost.id).is_default_site, False)

        # Now make the second site default
        response = self.post(
            {
                'default': True,
            },
            site_id=second_site.id
        )

        # Should redirect back to index
        self.assertRedirects(response, reverse('wagtailsites_index'))
        # Check that the second site is now set as default
        self.assertEqual(Site.objects.get(id=second_site.id).is_default_site, True)

    def test_making_a_second_site_the_default_not_allowed(self):
        second_site = Site.objects.create(
            hostname="also_default",
            port=80,
            is_default_site=False,
            root_page=self.home_page)
        response = self.post(
            {
                'default': True,
            },
            site_id=second_site.id
        )

        # Should return the form with errors
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bool(response.context['form'].errors), True)

        # Check that the site was not editd

        self.assertEqual(Site.objects.get(id=second_site.id).is_default_site, False)


class TestSiteDeleteView(TestCase, WagtailTestUtils):
    def setUp(self):
        self.login()
        self.home_page = Page.objects.get(id=2)
        self.localhost = Site.objects.all()[0]

    def get(self, params={}, site_id=None):
        return self.client.get(reverse('wagtailsites_delete', args=(site_id or self.localhost.id, )), params)

    def post(self, post_data={}, site_id=None):
        return self.client.post(reverse('wagtailsites_delete', args=(site_id or self.localhost.id, )), post_data)

    def test_simple(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailsites/confirm_delete.html')

    def test_nonexistant_redirect(self):
        self.assertEqual(self.get(site_id=100000).status_code, 404)

    def test_posting_deletes_site(self):
        response = self.post({
            'trivial_key': 'trivial_value'
        })

        # Should redirect back to index
        self.assertRedirects(response, reverse('wagtailsites_index'))

        # Check that the site was edited
        with self.assertRaises(Site.DoesNotExist):
            Site.objects.get(id=self.localhost.id)
