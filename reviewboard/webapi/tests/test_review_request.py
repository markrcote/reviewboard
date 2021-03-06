from django.contrib.auth.models import User, Permission
from django.db.models import Q
from djblets.testing.decorators import add_fixtures
from djblets.webapi.errors import DOES_NOT_EXIST, PERMISSION_DENIED

from reviewboard.reviews.models import ReviewRequest
from reviewboard.webapi.errors import INVALID_REPOSITORY
from reviewboard.webapi.tests.base import BaseWebAPITestCase
from reviewboard.webapi.tests.mimetypes import (review_request_item_mimetype,
                                                review_request_list_mimetype)
from reviewboard.webapi.tests.urls import (get_repository_item_url,
                                           get_review_request_item_url,
                                           get_review_request_list_url,
                                           get_user_item_url)


class ResourceListTests(BaseWebAPITestCase):
    """Testing the ReviewRequestResource list API tests."""
    fixtures = ['test_users']

    #
    # HTTP GET tests
    #

    @add_fixtures(['test_site'])
    def test_get(self):
        """Testing the GET review-requests/ API"""
        self.create_review_request(publish=True)
        self.create_review_request(publish=True)
        self.create_review_request(publish=True, with_local_site=True)

        rsp = self.apiGet(get_review_request_list_url(),
                          expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 2)

    @add_fixtures(['test_site'])
    def test_get_with_site(self):
        """Testing the GET review-requests/ API with a local site"""
        self._login_user(local_site=True)

        self.create_review_request(publish=True, with_local_site=True)
        self.create_review_request(publish=True, with_local_site=True,
                                   local_id=1002)
        self.create_review_request(publish=True)

        rsp = self.apiGet(get_review_request_list_url(self.local_site_name),
                          expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 2)

    @add_fixtures(['test_site'])
    def test_get_with_site_no_access(self):
        """Testing the GET review-requests/ API
        with a local site and Permission Denied error
        """
        self.apiGet(get_review_request_list_url(self.local_site_name),
                    expected_status=403)

    @add_fixtures(['test_site'])
    def test_get_with_status(self):
        """Testing the GET review-requests/?status= API"""
        self.create_review_request(publish=True, status='S')
        self.create_review_request(publish=True, status='S')
        self.create_review_request(publish=True, status='D')
        self.create_review_request(publish=True, status='P')
        self.create_review_request(publish=True, status='P')
        self.create_review_request(publish=True, status='P')

        url = get_review_request_list_url()

        rsp = self.apiGet(url, {'status': 'submitted'},
                          expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 2)

        rsp = self.apiGet(url, {'status': 'discarded'},
                          expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)

        rsp = self.apiGet(url, {'status': 'all'},
                          expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 6)

    def test_get_with_counts_only(self):
        """Testing the GET review-requests/?counts-only=1 API"""
        self.create_review_request(publish=True)
        self.create_review_request(publish=True)

        rsp = self.apiGet(get_review_request_list_url(), {
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'], 2)

    def test_get_with_to_groups(self):
        """Testing the GET review-requests/?to-groups= API"""
        group = self.create_review_group(name='devgroup')

        self.create_review_request(publish=True)

        review_request = self.create_review_request(publish=True)
        review_request.target_groups.add(group)

        rsp = self.apiGet(get_review_request_list_url(), {
            'to-groups': 'devgroup',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)

    def test_get_with_to_groups_and_status(self):
        """Testing the GET review-requests/?to-groups=&status= API"""
        group = self.create_review_group(name='devgroup')

        review_request = self.create_review_request(publish=True)
        review_request.target_groups.add(group)

        review_request = self.create_review_request(publish=True, status='S')
        review_request.target_groups.add(group)

        review_request = self.create_review_request(publish=True, status='D')
        review_request.target_groups.add(group)

        review_request = self.create_review_request(publish=True, status='D')
        review_request.target_groups.add(group)

        url = get_review_request_list_url()

        rsp = self.apiGet(url, {
            'status': 'submitted',
            'to-groups': 'devgroup',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)

        rsp = self.apiGet(url, {
            'status': 'discarded',
            'to-groups': 'devgroup',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 2)

    def test_get_with_to_groups_and_counts_only(self):
        """Testing the GET review-requests/?to-groups=&counts-only=1 API"""
        group = self.create_review_group(name='devgroup')

        review_request = self.create_review_request(publish=True)
        review_request.target_groups.add(group)

        review_request = self.create_review_request(publish=True)
        review_request.target_groups.add(group)

        rsp = self.apiGet(get_review_request_list_url(), {
            'to-groups': 'devgroup',
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'], 2)

    def test_get_with_to_users(self):
        """Testing the GET review-requests/?to-users= API"""
        grumpy = User.objects.get(username='grumpy')

        self.create_review_request(publish=True)

        review_request = self.create_review_request(publish=True)
        review_request.target_people.add(grumpy)

        review_request = self.create_review_request(publish=True)
        review_request.target_people.add(grumpy)

        rsp = self.apiGet(get_review_request_list_url(), {
            'to-users': 'grumpy',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 2)

    def test_get_with_to_users_and_status(self):
        """Testing the GET review-requests/?to-users=&status= API"""
        grumpy = User.objects.get(username='grumpy')

        self.create_review_request(publish=True)

        review_request = self.create_review_request(publish=True, status='S')
        review_request.target_people.add(grumpy)

        review_request = self.create_review_request(publish=True, status='D')
        review_request.target_people.add(grumpy)

        review_request = self.create_review_request(publish=True, status='D')
        review_request.target_people.add(grumpy)

        url = get_review_request_list_url()

        rsp = self.apiGet(url, {
            'status': 'submitted',
            'to-users': 'grumpy',
        }, expected_mimetype=review_request_list_mimetype)

        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)

        rsp = self.apiGet(url, {
            'status': 'discarded',
            'to-users': 'grumpy',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 2)

    def test_get_with_to_users_and_counts_only(self):
        """Testing the GET review-requests/?to-users=&counts-only=1 API"""
        grumpy = User.objects.get(username='grumpy')

        self.create_review_request(publish=True)

        review_request = self.create_review_request(publish=True)
        review_request.target_people.add(grumpy)

        review_request = self.create_review_request(publish=True)
        review_request.target_people.add(grumpy)

        rsp = self.apiGet(get_review_request_list_url(), {
            'to-users': 'grumpy',
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'], 2)

    @add_fixtures(['test_site'])
    def test_get_with_to_users_directly(self):
        """Testing the GET review-requests/?to-users-directly= API"""
        rsp = self.apiGet(get_review_request_list_url(), {
            'to-users-directly': 'doc',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']),
                         ReviewRequest.objects.to_user_directly("doc").count())

    def test_get_with_to_users_directly_and_status(self):
        """Testing the GET review-requests/?to-users-directly=&status= API"""
        url = get_review_request_list_url()

        rsp = self.apiGet(url, {
            'status': 'submitted',
            'to-users-directly': 'doc'
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            len(rsp['review_requests']),
            ReviewRequest.objects.to_user_directly("doc", status='S').count())

        rsp = self.apiGet(url, {
            'status': 'discarded',
            'to-users-directly': 'doc'
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            len(rsp['review_requests']),
            ReviewRequest.objects.to_user_directly("doc", status='D').count())

    def test_get_with_to_users_directly_and_counts_only(self):
        """Testing the
        GET review-requests/?to-users-directly=&counts-only=1 API
        """
        rsp = self.apiGet(get_review_request_list_url(), {
            'to-users-directly': 'doc',
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'],
                         ReviewRequest.objects.to_user_directly("doc").count())

    def test_get_with_from_user(self):
        """Testing the GET review-requests/?from-user= API"""
        rsp = self.apiGet(get_review_request_list_url(), {
            'from-user': 'grumpy',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']),
                         ReviewRequest.objects.from_user("grumpy").count())

    def test_get_with_from_user_and_status(self):
        """Testing the GET review-requests/?from-user=&status= API"""
        url = get_review_request_list_url()

        rsp = self.apiGet(url, {
            'status': 'submitted',
            'from-user': 'grumpy',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            len(rsp['review_requests']),
            ReviewRequest.objects.from_user("grumpy", status='S').count())

        rsp = self.apiGet(url, {
            'status': 'discarded',
            'from-user': 'grumpy',
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            len(rsp['review_requests']),
            ReviewRequest.objects.from_user("grumpy", status='D').count())

    def test_get_with_from_user_and_counts_only(self):
        """Testing the GET review-requests/?from-user=&counts-only=1 API"""
        rsp = self.apiGet(get_review_request_list_url(), {
            'from-user': 'grumpy',
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'],
                         ReviewRequest.objects.from_user("grumpy").count())

    @add_fixtures(['test_site'])
    def test_get_with_ship_it_0(self):
        """Testing the GET review-requests/?ship-it=0 API"""
        self.create_review_request(publish=True)

        review_request = self.create_review_request(publish=True)
        self.create_review(review_request, ship_it=True, publish=True)

        rsp = self.apiGet(get_review_request_list_url(), {
            'ship-it': 0,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)

        q = ReviewRequest.objects.public(user=self.user,
                                         status='P',
                                         extra_query=Q(shipit_count=0))
        self.assertEqual(len(rsp['review_requests']), q.count())

    @add_fixtures(['test_site'])
    def test_get_with_ship_it_1(self):
        """Testing the GET review-requests/?ship-it=1 API"""
        self.create_review_request(publish=True)

        review_request = self.create_review_request(publish=True)
        self.create_review(review_request, ship_it=True, publish=True)

        rsp = self.apiGet(get_review_request_list_url(), {
            'ship-it': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)

        q = ReviewRequest.objects.public(user=self.user,
                                         status='P',
                                         extra_query=Q(shipit_count__gt=0))
        self.assertEqual(len(rsp['review_requests']), q.count())

    @add_fixtures(['test_site'])
    def test_get_with_time_added_from(self):
        """Testing the GET review-requests/?time-added-from= API"""
        start_index = 3

        public_review_requests = [
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
        ]

        r = public_review_requests[start_index]
        timestamp = r.time_added.isoformat()

        rsp = self.apiGet(get_review_request_list_url(), {
            'time-added-from': timestamp,
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'],
                         len(public_review_requests) - start_index)
        self.assertEqual(
            rsp['count'],
            ReviewRequest.objects.filter(
                public=True, status='P',
                time_added__gte=r.time_added).count())

    @add_fixtures(['test_site'])
    def test_get_with_time_added_to(self):
        """Testing the GET review-requests/?time-added-to= API"""
        start_index = 3

        public_review_requests = [
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
        ]

        r = public_review_requests[start_index]
        timestamp = r.time_added.isoformat()

        rsp = self.apiGet(get_review_request_list_url(), {
            'time-added-to': timestamp,
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'],
                         len(public_review_requests) - start_index + 1)
        self.assertEqual(
            rsp['count'],
            ReviewRequest.objects.filter(
                public=True, status='P',
                time_added__lt=r.time_added).count())

    def test_get_with_last_updated_from(self):
        """Testing the GET review-requests/?last-updated-from= API"""
        start_index = 3
        public_review_requests = [
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
        ]

        r = public_review_requests[start_index]
        timestamp = r.last_updated.isoformat()

        rsp = self.apiGet(get_review_request_list_url(), {
            'last-updated-from': timestamp,
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'],
                         len(public_review_requests) - start_index)
        self.assertEqual(
            rsp['count'],
            ReviewRequest.objects.filter(
                public=True, status='P',
                last_updated__gte=r.last_updated).count())

    @add_fixtures(['test_site'])
    def test_get_with_last_updated_to(self):
        """Testing the GET review-requests/?last-updated-to= API"""
        start_index = 3
        public_review_requests = [
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
            self.create_review_request(publish=True),
        ]

        r = public_review_requests[start_index]
        timestamp = r.last_updated.isoformat()

        rsp = self.apiGet(get_review_request_list_url(), {
            'last-updated-to': timestamp,
            'counts-only': 1,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['count'],
                         len(public_review_requests) - start_index + 1)
        self.assertEqual(
            rsp['count'],
            ReviewRequest.objects.filter(
                public=True, status='P',
                last_updated__lt=r.last_updated).count())

    @add_fixtures(['test_scmtools'])
    def test_get_with_repository_and_changenum(self):
        """Testing the GET review-requests/?repository=&changenum= API"""
        review_request = self.create_review_request(create_repository=True,
                                                    publish=True)
        review_request.changenum = 1234
        review_request.save()

        rsp = self.apiGet(get_review_request_list_url(), {
            'repository': review_request.repository.id,
            'changenum': review_request.changenum,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)
        self.assertEqual(rsp['review_requests'][0]['id'],
                         review_request.display_id)
        self.assertEqual(rsp['review_requests'][0]['summary'],
                         review_request.summary)
        self.assertEqual(rsp['review_requests'][0]['changenum'],
                         review_request.changenum)
        self.assertEqual(rsp['review_requests'][0]['commit_id'],
                         review_request.commit)

    @add_fixtures(['test_scmtools'])
    def test_get_with_repository_and_commit_id(self):
        """Testing the GET review-requests/?repository=&commit_id= API
        with changenum backwards-compatibility
        """
        review_request = self.create_review_request(create_repository=True,
                                                    publish=True)
        review_request.changenum = 1234
        review_request.save()

        self.assertEqual(review_request.commit_id, None)

        commit_id = str(review_request.changenum)

        rsp = self.apiGet(get_review_request_list_url(), {
            'repository': review_request.repository.id,
            'commit_id': review_request.commit,
        }, expected_mimetype=review_request_list_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(len(rsp['review_requests']), 1)
        self.assertEqual(rsp['review_requests'][0]['id'],
                         review_request.display_id)
        self.assertEqual(rsp['review_requests'][0]['summary'],
                         review_request.summary)
        self.assertEqual(rsp['review_requests'][0]['changenum'],
                         review_request.changenum)
        self.assertEqual(rsp['review_requests'][0]['commit_id'],
                         commit_id)

    #
    # HTTP POST tests
    #

    @add_fixtures(['test_scmtools'])
    def test_post(self):
        """Testing the POST review-requests/ API"""
        repository = self.create_repository()

        rsp = self.apiPost(
            get_review_request_list_url(),
            {'repository': repository.path},
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            rsp['review_request']['links']['repository']['href'],
            self.base_url + get_repository_item_url(repository))

        # See if we can fetch this. Also return it for use in other
        # unit tests.
        return ReviewRequest.objects.get(pk=rsp['review_request']['id'])

    @add_fixtures(['test_scmtools'])
    def test_post_with_repository_name(self):
        """Testing the POST review-requests/ API with a repository name"""
        repository = self.create_repository()

        rsp = self.apiPost(
            get_review_request_list_url(),
            {'repository': repository.name},
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            rsp['review_request']['links']['repository']['href'],
            self.base_url + get_repository_item_url(repository))

        # See if we can fetch this. Also return it for use in other
        # unit tests.
        return ReviewRequest.objects.get(pk=rsp['review_request']['id'])

    @add_fixtures(['test_scmtools'])
    def test_post_with_no_repository(self):
        """Testing the POST review-requests/ API with no repository"""
        rsp = self.apiPost(
            get_review_request_list_url(),
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')

        self.assertFalse('repository' in rsp['review_request']['links'])

        # See if we can fetch this. Also return it for use in other
        # unit tests.
        review_request = ReviewRequest.objects.get(
            pk=rsp['review_request']['id'])
        self.assertEqual(review_request.repository, None)

    @add_fixtures(['test_site', 'test_scmtools'])
    def test_post_with_site(self):
        """Testing the POST review-requests/ API with a local site"""
        self._login_user(local_site=True)

        repository = self.create_repository(with_local_site=True)

        rsp = self.apiPost(
            get_review_request_list_url(self.local_site_name),
            {'repository': repository.path},
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['review_request']['links']['repository']['title'],
                         repository.name)

    @add_fixtures(['test_site', 'test_scmtools'])
    def test_post_with_site_no_access(self):
        """Testing the POST review-requests/ API
        with a local site and Permission Denied error
        """
        repository = self.create_repository(with_local_site=True)

        self.apiPost(
            get_review_request_list_url(self.local_site_name),
            {'repository': repository.path},
            expected_status=403)

    @add_fixtures(['test_site', 'test_scmtools'])
    def test_post_with_site_invalid_repository_error(self):
        """Testing the POST review-requests/ API
        with a local site and Invalid Repository error
        """
        repository = self.create_repository()

        self._login_user(local_site=True)
        rsp = self.apiPost(
            get_review_request_list_url(self.local_site_name),
            {'repository': repository.path},
            expected_status=400)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], INVALID_REPOSITORY.code)

    def test_post_with_invalid_repository_error(self):
        """Testing the POST review-requests/ API
        with Invalid Repository error
        """
        rsp = self.apiPost(
            get_review_request_list_url(),
            {'repository': 'gobbledygook'},
            expected_status=400)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], INVALID_REPOSITORY.code)

    @add_fixtures(['test_site', 'test_scmtools'])
    def test_post_with_no_site_invalid_repository_error(self):
        """Testing the POST review-requests/ API with
        Invalid Repository error from a site-local repository
        """
        repository = self.create_repository(with_local_site=True)

        rsp = self.apiPost(
            get_review_request_list_url(),
            {'repository': repository.path},
            expected_status=400)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], INVALID_REPOSITORY.code)

    @add_fixtures(['test_scmtools'])
    def test_post_with_submit_as(self):
        """Testing the POST review-requests/?submit_as= API"""
        self.user.is_superuser = True
        self.user.save()

        repository = self.create_repository()

        rsp = self.apiPost(
            get_review_request_list_url(),
            {
                'repository': repository.path,
                'submit_as': 'doc',
            },
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(
            rsp['review_request']['links']['repository']['href'],
            self.base_url + get_repository_item_url(repository))
        self.assertEqual(
            rsp['review_request']['links']['submitter']['href'],
            self.base_url + get_user_item_url('doc'))

        ReviewRequest.objects.get(pk=rsp['review_request']['id'])

    @add_fixtures(['test_scmtools'])
    def test_post_with_submit_as_and_permission_denied_error(self):
        """Testing the POST review-requests/?submit_as= API
        with Permission Denied error
        """
        repository = self.create_repository()

        rsp = self.apiPost(
            get_review_request_list_url(),
            {
                'repository': repository.path,
                'submit_as': 'doc',
            },
            expected_status=403)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], PERMISSION_DENIED.code)


class ResourceItemTests(BaseWebAPITestCase):
    """Testing the ReviewRequestResource item API tests."""
    fixtures = ['test_users']

    #
    # HTTP DELETE tests
    #

    def test_delete(self):
        """Testing the DELETE review-requests/<id>/ API"""
        self.user.user_permissions.add(
            Permission.objects.get(codename='delete_reviewrequest'))
        self.user.save()
        self.assertTrue(self.user.has_perm('reviews.delete_reviewrequest'))

        review_request = self.create_review_request(submitter=self.user,
                                                    publish=True)

        rsp = self.apiDelete(
            get_review_request_item_url(review_request.display_id))
        self.assertEqual(rsp, None)
        self.assertRaises(ReviewRequest.DoesNotExist,
                          ReviewRequest.objects.get,
                          pk=review_request.pk)

    def test_delete_with_permission_denied_error(self):
        """Testing the DELETE review-requests/<id>/ API
        with Permission Denied error
        """
        review_request = self.create_review_request(publish=True)
        self.assertNotEqual(review_request.submitter, self.user)

        rsp = self.apiDelete(
            get_review_request_item_url(review_request.display_id),
            expected_status=403)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], PERMISSION_DENIED.code)

    def test_delete_with_does_not_exist_error(self):
        """Testing the DELETE review-requests/<id>/ API
        with Does Not Exist error
        """
        self.user.user_permissions.add(
            Permission.objects.get(codename='delete_reviewrequest'))
        self.user.save()
        self.assertTrue(self.user.has_perm('reviews.delete_reviewrequest'))

        rsp = self.apiDelete(get_review_request_item_url(999),
                             expected_status=404)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], DOES_NOT_EXIST.code)

    @add_fixtures(['test_site'])
    def test_delete_with_site(self):
        """Testing the DELETE review-requests/<id>/ API with a lotal site"""
        user = User.objects.get(username='doc')
        user.user_permissions.add(
            Permission.objects.get(codename='delete_reviewrequest'))
        user.save()

        self._login_user(local_site=True)
        review_request = self.create_review_request(with_local_site=True)

        rsp = self.apiDelete(
            get_review_request_item_url(review_request.display_id,
                                        self.local_site_name))
        self.assertEqual(rsp, None)
        self.assertRaises(ReviewRequest.DoesNotExist,
                          ReviewRequest.objects.get, pk=review_request.pk)


    #
    # HTTP GET tests
    #

    @add_fixtures(['test_site'])
    def test_get(self):
        """Testing the GET review-requests/<id>/ API"""
        review_request = self.create_review_request(publish=True)

        rsp = self.apiGet(
            get_review_request_item_url(review_request.display_id),
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['review_request']['id'], review_request.display_id)
        self.assertEqual(rsp['review_request']['summary'],
                         review_request.summary)

    @add_fixtures(['test_site'])
    def test_get_with_site(self):
        """Testing the GET review-requests/<id>/ API with a local site"""
        self._login_user(local_site=True)
        review_request = self.create_review_request(publish=True,
                                                    with_local_site=True)

        rsp = self.apiGet(
            get_review_request_item_url(review_request.display_id,
                                        self.local_site_name),
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['review_request']['id'],
                         review_request.display_id)
        self.assertEqual(rsp['review_request']['summary'],
                         review_request.summary)

    @add_fixtures(['test_site'])
    def test_get_with_site_no_access(self):
        """Testing the GET review-requests/<id>/ API
        with a local site and Permission Denied error
        """
        group = self.create_review_group(with_local_site=True)
        review_request = self.create_review_request(with_local_site=True,
                                                    publish=True)
        review_request.target_groups.add(group)

        self.apiGet(get_review_request_item_url(review_request.display_id,
                                                self.local_site_name),
                    expected_status=403)

    def test_get_with_non_public_and_permission_denied_error(self):
        """Testing the GET review-requests/<id>/ API
        with non-public and Permission Denied error
        """
        review_request = self.create_review_request(public=False)
        self.assertNotEqual(review_request.submitter, self.user)

        rsp = self.apiGet(
            get_review_request_item_url(review_request.display_id),
            expected_status=403)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], PERMISSION_DENIED.code)

    def test_get_with_invite_only_group_and_permission_denied_error(self):
        """Testing the GET review-requests/<id>/ API
        with invite-only group and Permission Denied error
        """
        review_request = self.create_review_request(publish=True)
        self.assertNotEqual(review_request.submitter, self.user)

        group = self.create_review_group(invite_only=True)

        review_request.target_groups.add(group)
        review_request.save()

        rsp = self.apiGet(
            get_review_request_item_url(review_request.display_id),
            expected_status=403)
        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], PERMISSION_DENIED.code)

    @add_fixtures(['test_site'])
    def test_get_with_invite_only_group_and_target_user(self):
        """Testing the GET review-requests/<id>/ API
        with invite-only group and target user
        """
        review_request = self.create_review_request(publish=True)
        self.assertNotEqual(review_request.submitter, self.user)

        group = self.create_review_group(invite_only=True)

        review_request.target_groups.add(group)
        review_request.target_people.add(self.user)
        review_request.save()

        rsp = self.apiGet(
            get_review_request_item_url(review_request.display_id),
            expected_mimetype=review_request_item_mimetype)
        self.assertEqual(rsp['stat'], 'ok')
        self.assertEqual(rsp['review_request']['id'], review_request.display_id)
        self.assertEqual(rsp['review_request']['summary'],
                         review_request.summary)

    @add_fixtures(['test_site'])
    def test_get_not_modified(self):
        """Testing the GET review-requests/<id>/ API
        with Not Modified response
        """
        review_request = self.create_review_request(publish=True)

        self._testHttpCaching(get_review_request_item_url(review_request.id),
                              check_last_modified=True)

    #
    # HTTP PUT tests
    #

    def test_put_status_discarded(self):
        """Testing the PUT review-requests/<id>/?status=discarded API"""
        r = self.create_review_request(submitter=self.user, publish=True)

        rsp = self.apiPut(
            get_review_request_item_url(r.display_id),
            {
                'status': 'discarded',
                'description': 'comment',
            },
            expected_mimetype=review_request_item_mimetype)

        self.assertEqual(rsp['stat'], 'ok')

        r = ReviewRequest.objects.get(pk=r.id)
        self.assertEqual(r.status, 'D')

        c = r.changedescs.latest('timestamp')
        self.assertEqual(c.text, 'comment')

        fc_status = c.fields_changed['status']
        self.assertEqual(fc_status['old'][0], 'P')
        self.assertEqual(fc_status['new'][0], 'D')

    def test_put_status_discarded_with_permission_denied(self):
        """Testing the PUT review-requests/<id>/?status=discarded API
        with Permission Denied
        """
        r = self.create_review_request()
        self.assertNotEqual(r.submitter, self.user)

        rsp = self.apiPut(
            get_review_request_item_url(r.display_id),
            {'status': 'discarded'},
            expected_status=403)

        self.assertEqual(rsp['stat'], 'fail')
        self.assertEqual(rsp['err']['code'], PERMISSION_DENIED.code)

    def test_put_status_pending(self):
        """Testing the PUT review-requests/<id>/?status=pending API"""
        r = self.create_review_request(submitter=self.user, publish=True)
        r.close(ReviewRequest.SUBMITTED)
        r.save()

        rsp = self.apiPut(
            get_review_request_item_url(r.display_id),
            {'status': 'pending'},
            expected_mimetype=review_request_item_mimetype)

        self.assertEqual(rsp['stat'], 'ok')

        r = ReviewRequest.objects.get(pk=r.id)
        self.assertEqual(r.status, 'P')

    def test_put_status_submitted(self):
        """Testing the PUT review-requests/<id>/?status=submitted API"""
        r = self.create_review_request(submitter=self.user, publish=True)

        rsp = self.apiPut(
            get_review_request_item_url(r.display_id),
            {
                'status': 'submitted',
                'description': 'comment',
            },
            expected_mimetype=review_request_item_mimetype)

        self.assertEqual(rsp['stat'], 'ok')

        r = ReviewRequest.objects.get(pk=r.id)
        self.assertEqual(r.status, 'S')

        c = r.changedescs.latest('timestamp')
        self.assertEqual(c.text, 'comment')

        fc_status = c.fields_changed['status']
        self.assertEqual(fc_status['old'][0], 'P')
        self.assertEqual(fc_status['new'][0], 'S')

    @add_fixtures(['test_site'])
    def test_put_status_submitted_with_site(self):
        """Testing the PUT review-requests/<id>/?status=submitted API
        with a local site
        """
        self._login_user(local_site=True)
        r = self.create_review_request(submitter='doc', with_local_site=True,
                                       publish=True)

        rsp = self.apiPut(
            get_review_request_item_url(r.display_id, self.local_site_name),
            {
                'status': 'submitted',
                'description': 'comment'
            },
            expected_mimetype=review_request_item_mimetype)

        self.assertEqual(rsp['stat'], 'ok')

        r = ReviewRequest.objects.get(pk=r.id)
        self.assertEqual(r.status, 'S')

        c = r.changedescs.latest('timestamp')
        self.assertEqual(c.text, 'comment')

        fc_status = c.fields_changed['status']
        self.assertEqual(fc_status['old'][0], 'P')
        self.assertEqual(fc_status['new'][0], 'S')

    @add_fixtures(['test_site'])
    def test_put_status_submitted_with_site_no_access(self):
        """Testing the PUT review-requests/<id>/?status=submitted API
        with a local site and Permission Denied error
        """
        r = self.create_review_request(submitter='doc', with_local_site=True,
                                       publish=True)

        self.apiPut(
            get_review_request_item_url(r.display_id, self.local_site_name),
            {'status': 'submitted'},
            expected_status=403)
